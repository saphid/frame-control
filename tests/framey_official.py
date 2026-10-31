"""Pinned official Decky store archives used only in disposable test fixtures."""
from pathlib import Path


ROOT = Path(__file__).parent / 'fixtures/framey-official'
# Golden bytes after the exact managed frontend transformations. The full
# fake-Frame transport audit must not expect the original ZIP bytes here.
MANAGED_FRONTENDS = {
    131: '62f1fbb5636335bde268f0461d70dc03ee7ea2d2630f0e6957dba248523cd2e9',
    50: '76674318a475e2eeea8c6df4f44a7a5da5b07fac730b13b8b117365e28c75125',
    60: '34968b88fc828708680c1b82d774e76e8e11b5413222b9c508c10e1b7c375c78',
    130: '87dfd36612e6c049060b4147e3d99ebb8e500b292e7737491009bb51571e177a',
}
PLUGINS = (
    {'id': 66, 'name': 'PlayTime', 'version': '3.2.5', 'api_version': 1,
     'folder': 'SDH-PlayTime', 'sha256': '10fc3beea48991c77cb02867e919b618d4cd6d5e9c6a6d0ccd5266c13214039f'},
    {'id': 65, 'name': 'Decky Terminal', 'version': '0.5.3', 'api_version': 1,
     'folder': 'decky-terminal', 'sha256': '7bd8765ca57663a24178b05687acb52c3723518ac9eac1c14419a87904c0a872'},
    {'id': 143, 'name': 'Desktop Apps', 'version': '0.1.0', 'api_version': 1,
     'folder': 'decky-desktop-apps', 'sha256': '33fb674993c9b2bd119f0c6118c465e379f166ec1539c8183fcf7580f1d89577'},
    {'id': 117, 'name': 'DeckyParty File Manager', 'version': '1.0.0', 'api_version': 'legacy',
     'folder': 'Decky-CP', 'sha256': '193fb3aa0446fbc3c6bae0ae15700b5f04acebfa917b8e1791988c6ce832dddf'},
    {'id': 131, 'name': 'Download All', 'version': '1.1.0', 'api_version': 1,
     'folder': 'decky-download-all', 'sha256': '0641231eec139e3231e7b5369d0dbacefd686b52e3f2fffb39384876881408da'},
    {'id': 130, 'name': 'Games Prefix Manager', 'version': '1.0.1', 'api_version': 'legacy',
     'folder': 'GamesPrefixManager', 'sha256': 'ef8c727943188cad04c63fae7e4e620b8080c07f35dec0c144e99c6166307473'},
    {'id': 68, 'name': 'Wine Cellar', 'version': '0.2.1', 'api_version': 1,
     'folder': 'decky-wine-cellar', 'sha256': '7e077b933c234414d172b5c6d1c804b026bf39fa4e18e6663495a282637031e8'},
    {'id': 93, 'name': 'Deck Settings', 'version': '1.2.6', 'api_version': 1,
     'folder': 'decky-game-settings', 'sha256': '23c2a933a6883e2622f0184c33a76ce4a4e88c0a7dcd730f9bab71b8c3702132'},
    {'id': 52, 'name': 'Game Theme Music', 'version': '1.7.1-1', 'api_version': 1,
     'folder': 'SDH-GameThemeMusic', 'sha256': '9ce293ab4db212c03c6b96dfbc5e4d92e874d33387463f53223773921f75a80e'},
    {'id': 118, 'name': 'Speed Test', 'version': '1.0.2', 'api_version': 1,
     'folder': 'decky-speed-test', 'sha256': '8b1ee429aece9330b83ea3fc2e7e27d007ac61a737169f20bda3f1a19ab95508'},
    {'id': 28, 'name': 'Emuchievements', 'version': '2.0.5', 'api_version': 'legacy',
     'folder': 'Emuchievements', 'sha256': '98dcb443e81b9f9011cfe77c69eb659869c8e2df2df8b0a443df66cbfc2f5a89'},
    {'id': 67, 'name': 'Battery Tracker', 'version': '0.2.0', 'api_version': 'legacy',
     'folder': 'steam-deck-battery-tracker', 'sha256': '91c388d3c1b52079314045b79671ad55c767510658b6193f6936ed6cad383b94'},
    {'id': 114, 'name': 'Network Sentinel', 'version': '1.0.4', 'api_version': 1,
     'folder': 'network-sentinel', 'sha256': 'd3e07f40a0c800e72d15594e03c8c61e9bf3092524a578a0260520e735b971a5'},
    {'id': 13, 'name': 'Pause Games', 'version': '1.0.3', 'api_version': 1,
     'folder': 'SDH-PauseGames', 'sha256': '4aefdfb0ef25dea9c6d9fd037731c8b99ee8a1be966c2f7d5b0602112ef29f62'},
    {'id': 24, 'name': 'RadiYo!', 'version': '1.3', 'api_version': 'legacy',
     'folder': 'radiyo-steam-deck', 'sha256': '647111578aa7a5ecd16af8d7fe6c068a6d7ea8737c6dce5ac2d52e84a549ec43'},
    {'id': 132, 'name': 'SuggestMe', 'version': '1.5.3', 'api_version': 1,
     'folder': 'SuggestMe-decky-plugin', 'sha256': '248294b5d6b9d5a5d635ce35f4b5185ce59d4e4fd59353e24df4b29d74c2ade4'},
    {'id': 79, 'name': 'Decky Notifications', 'version': '1.0.1', 'api_version': 'legacy',
     'folder': 'decky-notifications', 'sha256': '3b22dc337209615f91da566ceb968793dc163b2e509de8535fb5d0fc55817312'},
    {'id': 104, 'name': 'Game Sync', 'version': '1.0.4', 'api_version': 1,
     'folder': 'SDH-GameSync', 'sha256': '65e021ebb37d2ebfbfbe3dbc8af95aef9556cf484730362c6b26c4ecc3e62ccd'},
    {'id': 60, 'name': 'DeckyFileServer', 'version': '1.2.0', 'api_version': 1,
     'folder': 'DeckyFileServer', 'sha256': '7dc2ecdcd05aa415d1ac90afaff28ecb17f77809a2bc7a77aee8e92505b976f0'},
    {'id': 125, 'name': 'Decky Localsend', 'version': '0.4.5', 'api_version': 1,
     'folder': 'decky-localsend', 'sha256': 'e271ccb55eb23f918b99a69f79aec905df4c9b2ef7b23bbf4ec1c2d1a6f0c6b7'},
    {'id': 89, 'name': 'DeckySpy', 'version': '0.6.7', 'api_version': 'legacy',
     'folder': 'decky-spy', 'sha256': '2d431a89826ed5cf3fd37258373eb3b46c841c39795aa8b25f83e59f4eee87c7'},
    {'id': 96, 'name': 'Simple Timer', 'version': '1.0.0', 'api_version': 1,
     'folder': 'simple-timer', 'sha256': '973d927e9d9a1feec04679c564af7e389a729b6735d2a988ffc2cb46ce4eb312'},
    {'id': 12, 'name': 'MusicControl', 'version': '1.1.6', 'api_version': 'legacy', 'folder': 'MusicControl', 'sha256': '246b89fd653c60a735b1cc401d1b0937d5cb969eea9024561661ff741f081d62'},
    {'id': 111, 'name': 'Music Control', 'version': '1.1.7', 'api_version': 'legacy',
     'folder': 'MusicControl', 'sha256': '3f56a3f56034b277ea74a2c37cc84133b69e382aa6bcb0b43876776aac737ed9'},
    {'id': 14, 'name': 'ProtonDB Badges', 'version': '1.3.4', 'api_version': 2,
     'folder': 'protondb-decky', 'sha256': '90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358'},
    {'id': 123, 'name': 'Steam Status', 'version': '1.2.3', 'api_version': 2,
     'folder': 'steamstatus-decky', 'sha256': '9053308e04a74f44745b45b9f4f50af3673348d367e7b14bacc5677de707ac4e'},
    {'id': 50, 'name': 'Storage Cleaner', 'version': '1.4.0', 'api_version': 1,
     'folder': 'decky-storage-cleaner', 'sha256': '1afa1a6f129c5d419de0e0bf0f6db8d8e50385a5659179346e996031ea372591'},
    {'id': 46, 'name': 'Steamback', 'version': '1.0.0-1', 'api_version': 'legacy',
     'folder': 'Steamback', 'sha256': 'ed5f2fbb47cdfc3aa9a4349a139ab20c29976117a3be0de7e8a588bb265ee7f3'},
    {'id': 18, 'name': 'Bluetooth', 'version': '3.1.1', 'api_version': 1,
     'folder': 'Bluetooth', 'sha256': 'f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5'},
    {'id': 26, 'name': 'HLTB for Deck', 'version': '2.0.12', 'api_version': 1,
     'folder': 'hltb-for-deck', 'sha256': 'bd54a23b0b8ec0798aa590e5be236522a593529d7680e77fb888e2971bf3d558'},
    {'id': 36, 'name': 'SteamGridDB', 'version': '1.8.1', 'api_version': 1,
     'folder': 'decky-steamgriddb', 'sha256': 'e84f5b1f111af8862b06218479491fbf61036e1bfd9f16f93f9901e9b9ebc5e0'},
    {'id': 53, 'name': 'Shotty', 'version': '0.1.0', 'api_version': 'legacy',
     'folder': 'Shotty', 'sha256': 'ab7f6618b264a0cb766525e788cef6c3e1478c0fef98a701225e5e8af441e2fe'},
    {'id': 63, 'name': 'Free Loader', 'version': '1.6.0', 'api_version': 1,
     'folder': 'free-loader', 'sha256': '05208aee6f6ba824391d8ddc81b1168b2599a9711e7528cdaa789f6cc710b42a'},
    {'id': 135, 'name': 'Deck Shelves', 'version': '2.0.0', 'api_version': 1,
     'folder': 'Deck-Shelves', 'sha256': 'b566280ad38fd3ecd584b5b46a855f301539eb9a86063834c64b7045f7063f91'},
)

# Upstream GitHub release asset, not the version currently listed by Decky's
# store. Keep it out of PLUGINS so fake-store fixtures remain truthful.
PREFIX_MANAGER_102 = {
    'id': 130, 'name': 'Games Prefix Manager', 'version': '1.0.2',
    'api_version': 'legacy', 'folder': 'games-prefix-manager',
    'sha256': '12ab420f06023cd13717489aa92a1babd09dec8566a601f4b4bb93464fbc92b6',
    'fixture': '130-v102.zip',
}

# This archive has a legacy IIFE frontend with no manifest API version.
LEGACY_PLUGINS = (
    {'id': 7, 'name': 'CSS Loader', 'version': '2.1.3', 'api_version': 'legacy',
     'folder': 'SDH-CssLoader', 'sha256': '99beaf1374af82408e6d056e0b0147e5fca544e1035fa7ab88419231697bc231'},
)


def archive(plugin):
    return (ROOT / plugin.get('fixture', f"{plugin['id']}.zip")).read_bytes()
