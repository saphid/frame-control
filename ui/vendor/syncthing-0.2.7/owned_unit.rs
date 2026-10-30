//! File ownership for the candidate's separate user unit. No DBus operations.
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

pub const UNIT: &str = "frame-control-syncthing";
const HEADER: &[u8] = b"# Frame Control managed Syncthing unit v1\n";
const LOCK: &[u8] = b"Frame Control Syncthing unit lock v1\n";
const LIMIT: u64 = 16 * 1024;
const NOFOLLOW: i32 = 0x20000; // Linux O_NOFOLLOW; helper targets Linux only.
static SEQUENCE: AtomicU64 = AtomicU64::new(0);

fn refused(reason: &str) -> io::Error {
    io::Error::new(io::ErrorKind::PermissionDenied, reason)
}

fn read_file(path: &Path, uid: u32) -> io::Result<Option<Vec<u8>>> {
    let meta = match fs::symlink_metadata(path) {
        Ok(meta) => meta,
        Err(err) if err.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(err) => return Err(err),
    };
    if !meta.is_file() || meta.uid() != uid || meta.nlink() != 1 || meta.len() > LIMIT {
        return Err(refused("Unit ownership file is not a bounded owned regular file"));
    }
    let file = OpenOptions::new().read(true).custom_flags(NOFOLLOW).open(path)?;
    let opened = file.metadata()?;
    if (meta.dev(), meta.ino()) != (opened.dev(), opened.ino()) {
        return Err(refused("Unit ownership file changed while opening"));
    }
    let mut bytes = Vec::new();
    file.take(LIMIT + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > LIMIT {
        return Err(refused("Unit ownership file exceeds its limit"));
    }
    Ok(Some(bytes))
}

pub struct OwnedUnit {
    unit: PathBuf,
    receipt: PathBuf,
    uid: u32,
    _lock: File,
}

/// Properties read afresh from the actual systemd manager, not from disk.
pub struct LoadedUnit {
    pub id: String,
    pub fragment: String,
    pub names: Vec<String>,
    pub drop_ins: Vec<String>,
    pub load_state: String,
    pub needs_reload: bool,
}

impl OwnedUnit {
    pub fn open(home: &Path) -> io::Result<Self> {
        let root = home.canonicalize()?;
        let uid = root.metadata()?.uid();
        if uid != fs::metadata("/proc/self")?.uid() {
            return Err(refused("Managed unit home is not owned by the current user"));
        }
        let mut directory = root;
        for component in [".config", "systemd", "user"] {
            directory.push(component);
            match fs::symlink_metadata(&directory) {
                Ok(meta) if meta.is_dir() && meta.uid() == uid && meta.mode() & 0o022 == 0 => (),
                Ok(_) => return Err(refused("Unit directory is not an owned real directory")),
                Err(err) if err.kind() == io::ErrorKind::NotFound => {
                    fs::DirBuilder::new().mode(0o700).create(&directory)?;
                },
                Err(err) => return Err(err),
            }
        }
        let path = directory.join(format!("{UNIT}.framey-lock"));
        match OpenOptions::new().write(true).create_new(true).mode(0o600).open(&path) {
            Ok(mut file) => { file.write_all(LOCK)?; file.sync_all()?; },
            Err(err) if err.kind() == io::ErrorKind::AlreadyExists => (),
            Err(err) => return Err(err),
        }
        if read_file(&path, uid)?.as_deref() != Some(LOCK) {
            return Err(refused("Unit lock belongs to another owner"));
        }
        let lock = OpenOptions::new().read(true).write(true).custom_flags(NOFOLLOW).open(&path)?;
        lock.try_lock().map_err(io::Error::other)?;
        let owned = Self { unit:directory.join(format!("{UNIT}.service")),
            receipt:directory.join(format!("{UNIT}.framey-owner")), uid, _lock:lock };
        owned.exists()?;
        Ok(owned)
    }

    /// A marker alone is insufficient: the sidecar must retain the exact bytes.
    pub fn exists(&self) -> io::Result<bool> {
        match (read_file(&self.unit, self.uid)?, read_file(&self.receipt, self.uid)?) {
            (None, None) => Ok(false),
            (Some(unit), Some(receipt)) if unit.starts_with(HEADER) && unit == receipt => Ok(true),
            _ => Err(refused("Existing Syncthing unit is unowned or was edited; preserved")),
        }
    }

    pub fn require(&self) -> io::Result<()> {
        if self.exists()? { Ok(()) } else { Err(refused("Managed Syncthing unit has not been created")) }
    }

    /// A receipt does not prove what the service manager would control. Keep
    /// overrides and aliases intact, and refuse rather than adopting them.
    pub fn verify_loaded(&self, loaded: &LoadedUnit) -> io::Result<()> {
        self.require()?;
        let name = format!("{UNIT}.service");
        if loaded.load_state != "loaded" || loaded.id != name ||
            loaded.names != [name] || Path::new(&loaded.fragment) != self.unit ||
            !loaded.drop_ins.is_empty() || loaded.needs_reload {
            return Err(refused("Loaded Syncthing unit differs from owned fragment or has overrides; preserved"));
        }
        Ok(())
    }

    pub fn write(&self, contents: &[u8]) -> io::Result<()> {
        if !contents.starts_with(HEADER) || contents.len() as u64 > LIMIT {
            return Err(refused("Invalid managed Syncthing unit contents"));
        }
        let exists = self.exists()?;
        if exists && read_file(&self.unit, self.uid)?.as_deref() == Some(contents) {
            return Ok(());
        }
        if exists {
            // Our shared lock serializes candidates. A torn two-file update
            // fails closed on the next operation, retaining both copies.
            let mode = fs::symlink_metadata(&self.unit)?.permissions().mode() & 0o777;
            self.replace(&self.unit, contents, mode)?;
            self.replace(&self.receipt, contents, 0o600)?;
        } else {
            self.create(&self.unit, contents, 0o644)?;
            // If receipt creation fails, preserve the unit and refuse future
            // operations. Never remove a path that could have changed owners.
            self.create(&self.receipt, contents, 0o600)?;
        }
        Ok(())
    }

    pub fn remove(&self) -> io::Result<()> {
        if self.exists()? {
            fs::remove_file(&self.unit)?;
            fs::remove_file(&self.receipt)?;
        }
        // Retain the lock inode so two candidates cannot lock different files.
        Ok(())
    }

    fn create(&self, path: &Path, contents: &[u8], mode: u32) -> io::Result<()> {
        let mut file = OpenOptions::new().write(true).create_new(true).mode(mode).open(path)?;
        file.write_all(contents)?;
        file.sync_all()
    }

    fn replace(&self, path: &Path, contents: &[u8], mode: u32) -> io::Result<()> {
        let temporary = self.unit.with_file_name(format!(".{UNIT}.{}-{}.tmp", std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)));
        self.create(&temporary, contents, mode)?;
        let result = fs::rename(&temporary, path);
        if result.is_err() { fs::remove_file(&temporary)?; }
        result
    }
}

pub fn render(flatpak: &str, app: &str, command: &str) -> io::Result<Vec<u8>> {
    let token = |s: &str| !s.is_empty() && s.len() <= 256 && s.bytes()
        .all(|b| b.is_ascii_alphanumeric() || b"._-/".contains(&b));
    if !flatpak.starts_with('/') || !token(flatpak) || !token(app) || app.contains('/') ||
        !token(command) || app.starts_with('-') || command.starts_with('-') {
        return Err(refused("Flatpak unit arguments must be bounded literal tokens"));
    }
    Ok(format!("{}[Unit]\nDescription=Frame Control managed Syncthing\n\n[Service]\nExecStart={} run --die-with-parent --command={} {} --no-browser --no-restart\nRestart=on-failure\nSuccessExitStatus=3 4\nRestartForceExitStatus=3 4\n\n[Install]\nWantedBy=default.target\n",
        String::from_utf8_lossy(HEADER), flatpak, command, app).into_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;

    struct Home(PathBuf);
    impl Home {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!("framey-unit-test-{}-{}", std::process::id(),
                SEQUENCE.fetch_add(1, Ordering::Relaxed)));
            fs::create_dir(&path).unwrap();
            Self(path)
        }
        fn unit(&self) -> PathBuf { self.0.join(".config/systemd/user").join(format!("{UNIT}.service")) }
    }
    impl Drop for Home { fn drop(&mut self) { fs::remove_dir_all(&self.0).unwrap(); } }
    fn bytes() -> Vec<u8> { render("/usr/bin/flatpak", "me.kozec.syncthingtk", "syncthing").unwrap() }

    fn loaded(home: &Home) -> LoadedUnit {
        LoadedUnit { id:format!("{UNIT}.service"), fragment:home.unit().to_str().unwrap().to_owned(),
            names:vec![format!("{UNIT}.service")], drop_ins:vec![], load_state:"loaded".to_owned(),
            needs_reload:false }
    }

    #[test]
    fn loaded_unit_requires_receipt_and_exact_manager_identity() {
        let home = Home::new();
        let owned = OwnedUnit::open(&home.0).unwrap();
        assert!(owned.verify_loaded(&loaded(&home)).is_err());
        owned.write(&bytes()).unwrap();
        owned.verify_loaded(&loaded(&home)).unwrap();
        let mut foreign = loaded(&home);
        foreign.fragment = "/run/user/1100/systemd/user/frame-control-syncthing.service".to_owned();
        assert!(owned.verify_loaded(&foreign).is_err());
        foreign = loaded(&home);
        foreign.id = "foreign.service".to_owned();
        assert!(owned.verify_loaded(&foreign).is_err());
        assert_eq!(fs::read(home.unit()).unwrap(), bytes());
    }

    #[test]
    fn dropins_aliases_stale_and_unloaded_units_are_refused() {
        let home = Home::new();
        let owned = OwnedUnit::open(&home.0).unwrap();
        owned.write(&bytes()).unwrap();
        let mut changed = loaded(&home);
        changed.drop_ins.push("/private/override.conf".to_owned());
        assert!(owned.verify_loaded(&changed).is_err());
        changed = loaded(&home);
        changed.names.push("foreign-alias.service".to_owned());
        assert!(owned.verify_loaded(&changed).is_err());
        changed = loaded(&home);
        changed.needs_reload = true;
        assert!(owned.verify_loaded(&changed).is_err());
        for state in ["not-found", "error", "masked", "merged"] {
            changed = loaded(&home);
            changed.load_state = state.to_owned();
            assert!(owned.verify_loaded(&changed).is_err());
        }
        assert_eq!(fs::read(home.unit()).unwrap(), bytes());
    }

    #[test]
    fn own_create_update_remove_preserves_legacy_unit_and_lock() {
        let home = Home::new();
        let owned = OwnedUnit::open(&home.0).unwrap();
        let legacy = home.unit().with_file_name("decky-syncthing.service");
        fs::write(&legacy, b"pre-existing legacy unit").unwrap();
        owned.write(&bytes()).unwrap();
        let changed = render("/usr/bin/flatpak", "example.Other", "syncthing").unwrap();
        owned.write(&changed).unwrap();
        assert_eq!(fs::read(home.unit()).unwrap(), changed);
        owned.remove().unwrap();
        assert!(!home.unit().exists());
        assert_eq!(fs::read(legacy).unwrap(), b"pre-existing legacy unit");
        assert!(home.unit().with_file_name(format!("{UNIT}.framey-lock")).exists());
    }

    #[test]
    fn preexisting_unit_without_receipt_is_preserved() {
        let home = Home::new();
        drop(OwnedUnit::open(&home.0).unwrap());
        fs::write(home.unit(), b"foreign service").unwrap();
        assert!(OwnedUnit::open(&home.0).is_err());
        assert_eq!(fs::read(home.unit()).unwrap(), b"foreign service");
    }

    #[test]
    fn edited_owned_unit_refuses_update_and_removal() {
        let home = Home::new();
        let owned = OwnedUnit::open(&home.0).unwrap();
        owned.write(&bytes()).unwrap();
        fs::write(home.unit(), b"user edit").unwrap();
        assert!(owned.write(&bytes()).is_err());
        assert!(owned.remove().is_err());
        assert_eq!(fs::read(home.unit()).unwrap(), b"user edit");
    }

    #[test]
    fn symlink_unit_and_config_directory_preserve_targets() {
        let home = Home::new();
        let target = home.0.join("private-marker");
        fs::write(&target, b"preserve").unwrap();
        drop(OwnedUnit::open(&home.0).unwrap());
        symlink(&target, home.unit()).unwrap();
        assert!(OwnedUnit::open(&home.0).is_err());
        assert_eq!(fs::read(&target).unwrap(), b"preserve");
        let other = Home::new();
        symlink(&home.0, other.0.join(".config")).unwrap();
        assert!(OwnedUnit::open(&other.0).is_err());
        assert_eq!(fs::read(target).unwrap(), b"preserve");
    }

    #[test]
    fn hardlink_unit_and_corrupt_receipt_are_refused() {
        let home = Home::new();
        let owned = OwnedUnit::open(&home.0).unwrap();
        owned.write(&bytes()).unwrap();
        let target = home.0.join("retained");
        fs::hard_link(home.unit(), &target).unwrap();
        assert!(owned.remove().is_err());
        fs::remove_file(&target).unwrap();
        fs::write(&owned.receipt, b"different receipt").unwrap();
        assert!(owned.remove().is_err());
        assert_eq!(fs::read(home.unit()).unwrap(), bytes());
    }

    #[test]
    fn concurrent_owner_is_refused_and_lock_inode_reused() {
        let home = Home::new();
        let owned = OwnedUnit::open(&home.0).unwrap();
        assert!(OwnedUnit::open(&home.0).is_err());
        let inode = owned._lock.metadata().unwrap().ino();
        drop(owned);
        assert_eq!(OwnedUnit::open(&home.0).unwrap()._lock.metadata().unwrap().ino(), inode);
    }

    #[test]
    fn literal_arguments_refuse_unit_injection_and_expansion() {
        for value in ["", "name\nExecStart=/bin/false", "%h", "$HOME", "a b", "-override"] {
            assert!(render("/usr/bin/flatpak", value, "syncthing").is_err());
            assert!(render("/usr/bin/flatpak", "example.App", value).is_err());
        }
        assert!(render("relative/flatpak", "example.App", "syncthing").is_err());
    }

    #[test]
    fn missing_or_torn_ownership_cannot_control_a_service() {
        let home = Home::new();
        let owned = OwnedUnit::open(&home.0).unwrap();
        assert!(owned.require().is_err());
        fs::write(&owned.receipt, bytes()).unwrap();
        assert!(owned.write(&bytes()).is_err());
        assert!(!home.unit().exists());
    }

    #[test]
    fn new_directories_are_private_and_writable_shared_parent_is_refused() {
        let home = Home::new();
        drop(OwnedUnit::open(&home.0).unwrap());
        for path in [".config", ".config/systemd", ".config/systemd/user"] {
            assert_eq!(fs::metadata(home.0.join(path)).unwrap().mode() & 0o777, 0o700);
        }
        fs::set_permissions(home.0.join(".config/systemd"), fs::Permissions::from_mode(0o770)).unwrap();
        assert!(OwnedUnit::open(&home.0).is_err());
        assert!(!home.unit().exists());
    }
}
