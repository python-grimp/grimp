import pytest

import grimp


@pytest.fixture(params=["python", "rust"])
def build_graph(request):
    """
    Provides each implementation of build_graph, so that the functional tests cover both.
    """
    return grimp.build_graph if request.param == "python" else grimp.build_graph_rust
