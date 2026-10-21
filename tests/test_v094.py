from localscope.models import FileNode
from localscope.smart_categories import build_purpose_report


def file(path, size):
    return FileNode(path.rsplit('\\', 1)[-1], path, size)


def directory(path, children):
    return FileNode(path.rsplit('\\', 1)[-1], path, sum(c.size for c in children), True, children)


def totals(root):
    return {x.purpose: x.bytes for x in build_purpose_report(root).totals}


def test_system_files_and_app_cache():
    root = directory('C:\\', [
        file(r'C:\pagefile.sys', 100), file(r'C:\hiberfil.sys', 40),
        directory(r'C:\Users\a\AppData\Local\NVIDIA\DXCache', [file(r'C:\Users\a\AppData\Local\NVIDIA\DXCache\x.nvph', 20)]),
        file(r'C:\mystery.zzz', 3)])
    result = totals(root)
    assert result['System'] == 140
    assert result['Applications'] == 20
    assert result['Other'] == 3
    assert sum(result.values()) == 163


def test_gog_and_minecraft_and_ollama():
    root = directory('C:\\', [
        directory(r'C:\Program Files (x86)\GOG Galaxy\Games\Cyberpunk 2077', [file(r'C:\Program Files (x86)\GOG Galaxy\Games\Cyberpunk 2077\game.bin', 80)]),
        directory(r'C:\Users\a\AppData\Roaming\.minecraft', [file(r'C:\Users\a\AppData\Roaming\.minecraft\saves\world.mca', 30)]),
        directory(r'C:\Users\a\.ollama\models', [file(r'C:\Users\a\.ollama\models\blobs\sha256-abc', 15)]),
    ])
    result = totals(root)
    assert result['Games'] == 110
    assert result['Development'] == 15
    assert sum(result.values()) == 125


def test_dll_in_game_not_other():
    game = directory(r'C:\Steam\steamapps\common\Example', [file(r'C:\Steam\steamapps\common\Example\game.dll', 10)])
    assert totals(game)['Games'] == 10
