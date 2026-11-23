import os
import random

import pytest

from agentdb.reproducibility import SeedReport, make_generator, seed_worker, set_global_seed


def test_set_seed_makes_python_random_reproducible():
    set_global_seed(123)
    first = [random.random() for _ in range(5)]
    set_global_seed(123)
    second = [random.random() for _ in range(5)]
    assert first == second


def test_report_marks_python_and_hashseed():
    report = set_global_seed(7)
    assert isinstance(report, SeedReport)
    assert report.seed == 7
    assert report.python is True
    assert os.environ["PYTHONHASHSEED"] == "7"


def test_negative_seed_raises():
    with pytest.raises(ValueError, match="非负整数"):
        set_global_seed(-1)


def test_numpy_reproducible_if_available():
    np = pytest.importorskip("numpy")
    report = set_global_seed(99)
    assert report.numpy is True
    first = np.random.rand(4)
    set_global_seed(99)
    second = np.random.rand(4)
    assert (first == second).all()


def test_seed_worker_reseeds_python_random_deterministically():
    seed_worker(3)
    first = [random.random() for _ in range(4)]
    seed_worker(3)
    second = [random.random() for _ in range(4)]
    assert first == second


def test_make_generator_seeded_if_torch_available():
    torch = pytest.importorskip("torch")
    g1 = make_generator(42)
    g2 = make_generator(42)
    assert g1 is not None
    a = torch.rand(4, generator=g1)
    b = torch.rand(4, generator=g2)
    assert torch.equal(a, b)
