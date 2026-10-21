from types import SimpleNamespace
from localscope.relationship_model import relationship_data

def test_graph_links_and_unlinked_project():
    report = SimpleNamespace(
        links=[SimpleNamespace(path='C:/work/demo/.venv', size=1024, project='C:/work/demo',
             base_executable='C:/Python312/python.exe', version='3.12', installed_packages=3,
             state='Linked', confidence='High')],
        audit=SimpleNamespace(projects=[SimpleNamespace(path='C:/work/demo'), SimpleNamespace(path='C:/work/other')]))
    nodes, edges = relationship_data(report)
    assert len(nodes) == 4
    assert len(edges) == 2
    assert any(v[1] == 'Base reference' for v in nodes.values())
