from pathlib import Path


def test_optimization_center_has_explicit_scope_selection():
    source = (Path(__file__).resolve().parents[1] / 'src' / 'localscope' / 'optimization_ui.py').read_text(encoding='utf-8')
    assert 'Analysis scope:' in source
    assert 'QFileDialog.getExistingDirectory' in source
    assert 'target = scan(self.scope_path' in source
    assert 'DuplicateWorker(self.root, self.scope_path)' in source
