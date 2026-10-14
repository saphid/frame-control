"""Store categories that make sense on a Steam Frame, and which apps only make sense on a phone.

Sources describe apps in their own terms (F-Droid's categories, a VR flag). The store groups
them for a headset instead: VR first, then games and the flat apps worth having in a panel
(video, reading, making things). Apps built around a phone's hardware or system (calls and
SMS, launchers, widgets, keyboards, fitness, root tools) are marked phone_only; the store
hides them unless asked, since Lepton can run them but they do nothing useful on the Frame.
"""
import re

# (id, label), in the order the store shows them.
CATEGORIES = (
    ('vr', 'VR'),
    ('games', 'Games'),
    ('emulators', 'Emulators'),
    ('watch', 'Watch & listen'),
    ('read', 'Read & learn'),
    ('create', 'Create'),
    ('work', 'Work'),
    ('web', 'Web & chat'),
    ('tools', 'Tools'),
)
IDS = {c for c, _ in CATEGORIES}

# F-Droid's category names -> a store category; None = only useful on a phone.
# F-Droid has broad categories ('Multimedia') and, since 2025, finer ones ('Podcast'); an app
# usually has both. A finer one decides, since 'Social Network' + 'Multimedia' is a chat app.
BROAD = {
    'Games': 'games', 'Multimedia': 'watch', 'Reading': 'read', 'Science & Education': 'read',
    'Graphics': 'create', 'Writing': 'work', 'Money': 'work', 'Time': 'work', 'Internet': 'web',
    'Development': 'tools', 'Security': 'tools',
    'Office': 'work', 'Food': 'read',  # IzzyOnDroid's own names
    'Connectivity': None, 'Navigation': None, 'Phone & SMS': None, 'Sports & Health': None,
    'System': None, 'Theming': None,
}
FINE = {
    'emulators': ('Emulator',),
    'games': ('Action Game', 'Board Game', 'Card Game', 'Casual Game', 'Dice', 'Educational Game', 'Party Game',
              'Platformer Game', 'Puzzle Game', 'Role-Playing Game', 'Shooter Game', 'Sport Game',
              'Strategy Game', 'Visual Novel', 'Word Game'),
    'watch': ('Local Media Player', 'Online Media Player', 'Podcast', 'Radio', 'Cast', 'Lyrics', 'Gallery',
              'Ambient Sound'),
    'read': ('Ebook Reader', 'Audiobook', 'News', 'Translation & Dictionary', 'Religion', 'Recipe Manager'),
    'create': ('Draw', 'Music Practice Tool', 'Recorder'),
    'web': ('Browser', 'Email', 'Messaging', 'Social Network', 'Forum', 'Voice & Video Chat', 'AI Chat',
            'Bookmark'),
    'work': ('Note', 'Task', 'Text Editor', 'Calendar & Agenda', 'Calculator', 'Unit Convertor',
             'Finance Manager', 'Time Tracker', 'Schedule', 'Inventory'),
    'tools': ('Code & Forge', 'Password & 2FA', 'File Manager', 'File Encryption & Vault', 'Text Encryption',
              'Remote Access', 'Remote Controller', 'Cloud Storage & File Sync', 'Network Analyzer',
              'File Transfer', 'Text to Speech', 'Speech Recognizer', 'Download', 'Game Helper', 'Weather'),
}
FINE_TARGET = {name: target for target, names in FINE.items() for name in names}
# Only make sense as part of a phone's own system: any one of these makes an app phone-only.
PHONE_SYSTEM = {
    'Launcher', 'Keyboard & IME', 'Phone & SMS', 'Wallpaper', 'Icon Pack', 'Flashlight', 'Battery',
    'Notification', 'Volume', 'Theming', 'Emergency Action', 'Push', 'Xposed', 'Automation',
}
# Phone things that are often a side of a useful app (Thunderbird is in Contact, Nextcloud in
# Connectivity, a file manager in System): phone-only unless a finer useful category says otherwise.
PHONE_SIDE = {
    'Contact', 'Camera', 'OCR', 'Location Tracker & Sharer', 'Navigation', 'Public Transport', 'Workout',
    'Diet', 'Medication', 'Health Manager', 'Alarm Clock', 'Pass Wallet', 'Wallet', 'VPN & Proxy',
    'DNS & Hosts', 'Firewall', 'App Manager', 'App Store & Updater', 'System', 'Connectivity',
}
PHONE_CATEGORIES = PHONE_SYSTEM | PHONE_SIDE
# Fine categories that aren't useful on a headset either, but don't make an app phone-only on their own.
PHONE_LEANING = {'Clock', 'Timer', 'Stopwatch', 'Habit Tracker', 'Shopping List', 'Market & Price',
                 'Meditation', 'Mental Health', 'Sports & Health'}
# When an app has several, the one that best describes it on a headset wins.
PRIORITY = ('emulators', 'games', 'watch', 'read', 'create', 'web', 'work', 'tools')

EMULATOR = re.compile(r'\bemulat(or|ion|es)\b|\b(retroarch|ppsspp|dolphin|dosbox|scummvm|mame|mupen64|melonds|citra|duckstation|flycast)\b', re.I)
# "No root needed" isn't a root tool.
NOT_ROOT = re.compile(r'\b(no|non|without|not|never|doesn.?t (need|require)|does not (need|require))[- ]+(the )?root(ed|ing)?\b'
                      r'|\broot(less|[- ]free| (is )?not (required|needed))\b', re.I)
# Phone-only by what it is, whatever its category says.
PHONE = re.compile(r'\b(launcher|home ?screen|widgets?|keyboard|wallpapers?|ringtones?|dialer|sms|mms|'
                   r'call (log|block|record)|caller id|lock ?screen|status ?bar|notification (shade|panel)|'
                   r'step counter|pedometer|nfc|sim card|5g|4g|lte|hotspot|tethering|root(ed)?|magisk|xposed|'
                   r'battery (saver|monitor|charge))\b|\[root\]', re.I)


def classify(entry):
    """{'category': one of IDS or None, 'phone_only': bool} for a store entry."""
    if entry.get('vr') is True:
        return {'category': 'vr', 'phone_only': False}
    text = NOT_ROOT.sub(' ', ' '.join(str(entry.get(k) or '') for k in ('name', 'summary')))
    names = [c for c in entry.get('categories') or () if isinstance(c, str)]
    fine = {FINE_TARGET[c] for c in names if c in FINE_TARGET}
    broad = {BROAD[c] for c in names if BROAD.get(c)}
    category = next((c for c in PRIORITY if c in fine), None) or next((c for c in PRIORITY if c in broad), None)
    if category is None and EMULATOR.search(text):
        category = 'emulators'
    phone = any(c in PHONE_SYSTEM for c in names) or (not fine and any(c in PHONE_SIDE for c in names))
    if names and category is None and all(c in PHONE_CATEGORIES or c in PHONE_LEANING or BROAD.get(c, 1) is None
                                          for c in names):
        phone = True
    if category not in ('games', 'emulators', 'watch', 'read', 'create') and PHONE.search(text):
        phone = True
    return {'category': category, 'phone_only': phone}


def matches(entry, category=None, phone=False):
    """Whether a classified entry belongs in a browse for this category ('' or None = any)."""
    if entry.get('phone_only') and not phone:
        return False
    return not category or entry.get('category') == category
