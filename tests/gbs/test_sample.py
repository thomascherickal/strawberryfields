# Copyright 2019 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
r"""
Unit tests for strawberryfields.gbs.sample
"""
# pylint: disable=no-self-use,unused-argument,protected-access
import networkx as nx
import numpy as np
import pytest

import strawberryfields as sf
from strawberryfields.gbs import sample

pytestmark = pytest.mark.gbs

samples_pnr_nopostselect = np.array(
    [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 1, 1],
        [1, 1, 0, 0],
        [2, 1, 3, 4],
        [2, 0, 1, 3],
        [0, 0, 0, 0],
        [1, 2, 1, 0],
        [0, 0, 0, 0],
    ]
)

sample_number = len(samples_pnr_nopostselect)
integration_sample_number = 2

sample_pnr_postselect = np.array([[2, 0, 1, 3]])
sample_threshold_postselect = np.array([[1, 0, 1, 1]])

adj_dim_range = range(2, 6)


@pytest.mark.parametrize("dim", [4])
class TestSample:
    """Tests for the function ``strawberryfields.gbs.sample.sample``"""

    def test_invalid_adjacency(self, dim):
        """Test if function raises a ``ValueError`` for a matrix that is not symmetric"""
        with pytest.raises(ValueError, match="Input must be a NumPy array"):
            adj_asym = np.triu(np.ones((dim, dim)))
            sample.sample(A=adj_asym, n_mean=1.0)

    def test_invalid_samples(self, adj, monkeypatch):
        """Test if function raises a ``ValueError`` when a number of samples less than one is
        requested """
        with pytest.raises(ValueError, match="Number of samples must be at least one"):
            sample.sample(A=adj, n_mean=1.0, samples=0)

    def test_badpostselect(self, adj):
        """Tests if function raises a ``ValueError`` when a negative value is set for
        ``postselect`` """
        with pytest.raises(ValueError, match="Can only postselect on nonnegative values"):
            sample.sample(
                A=adj, n_mean=1.0, samples=sample_number, backend_options={"postselect": -1}
            )

    @pytest.mark.parametrize("valid_backends", sample.QUANTUM_BACKENDS)
    def test_pnr_nopostselect(self, adj, monkeypatch, valid_backends):
        """Test if function returns correct samples with no additional manipulation, i.e.,
        no postselection or threshold detection """

        def dummy_sample_sf(*args, **kwargs):
            """Dummy ``_sample_sf`` function"""
            return samples_pnr_nopostselect

        with monkeypatch.context() as m:
            m.setattr(sample, "_sample_sf", dummy_sample_sf)
            samples = sample.sample(
                A=adj,
                n_mean=1.0,
                samples=sample_number,
                backend_options={"backend": valid_backends, "threshold": False, "postselect": 0},
            )

        assert np.allclose(samples_pnr_nopostselect, samples)

    @pytest.mark.parametrize("valid_backends", sample.QUANTUM_BACKENDS)
    def test_threshold_nopostselect(self, adj, monkeypatch, valid_backends):
        """Test if function returns correct samples when threshold detection is used and no
        postselection on samples. With threshold detection, all non-zero elements of a sample are
        set to 1. """

        samples_threshold_nopostselect = samples_pnr_nopostselect.copy()
        samples_threshold_nopostselect[samples_threshold_nopostselect >= 1] = 1

        def dummy_sample_sf(*args, **kwargs):
            """Dummy ``_sample_sf`` function"""
            return samples_pnr_nopostselect

        with monkeypatch.context() as m:
            m.setattr(sample, "_sample_sf", dummy_sample_sf)
            samples = np.array(
                sample.sample(
                    A=adj,
                    n_mean=1.0,
                    samples=sample_number,
                    backend_options={"backend": valid_backends, "threshold": True, "postselect": 0},
                )
            )

        assert set(tuple(samples.flatten())) == {0, 1}
        assert np.allclose(samples, samples_threshold_nopostselect)

    @pytest.mark.parametrize("valid_backends", sample.QUANTUM_BACKENDS)
    def test_pnr_postselect(self, adj, monkeypatch, valid_backends):
        """Test if function returns samples when photon-number resolving detection is used and
        postselection. Postselection only returns samples with a total photon number not less
        than the parameter specified. """

        def dummy_sample_sf(*args, **kwargs):
            """Dummy ``_sample_sf`` function"""
            return sample_pnr_postselect

        with monkeypatch.context() as m:
            m.setattr(sample, "_sample_sf", dummy_sample_sf)
            samples = np.array(
                sample.sample(
                    A=adj,
                    n_mean=1.0,
                    samples=sample_number,
                    backend_options={
                        "backend": valid_backends,
                        "threshold": False,
                        "postselect": 1,
                    },
                )
            )

        samples_target = np.array([sample_pnr_postselect[0] for _ in range(sample_number)])

        assert np.allclose(samples, samples_target)

    @pytest.mark.parametrize("valid_backends", sample.QUANTUM_BACKENDS)
    def test_threshold_postselect(self, adj, monkeypatch, valid_backends):
        """Test if function returns samples when threshold detection is used and postselection.
        With threshold detection, all non-zero elements of a sample are set to 1. Postselection
        only returns samples with a total click number (number of 1's) not less than the
        parameter specified. """

        def dummy_sample_sf(*args, **kwargs):
            """Dummy ``_sample_sf`` function"""
            return sample_pnr_postselect

        with monkeypatch.context() as m:
            m.setattr(sample, "_sample_sf", dummy_sample_sf)
            samples = np.array(
                sample.sample(
                    A=adj,
                    n_mean=1.0,
                    samples=sample_number,
                    backend_options={"backend": valid_backends, "threshold": True, "postselect": 1},
                )
            )

        samples_target = np.array([sample_pnr_postselect[0] for _ in range(sample_number)])
        samples_target[samples_target >= 1] = 1

        assert np.allclose(samples, samples_target)


@pytest.mark.parametrize("dim", adj_dim_range)
class TestSampleIntegration:
    """Integration tests for the function ``strawberryfields.gbs.sample.sample``"""

    def test_pnr_nopostselect_integration(self, adj):
        """Integration test to check if function returns samples of correct form, i.e., correct
        number of samples, correct number of modes, all non-negative integers """
        samples = np.array(
            sample.sample(
                A=adj,
                n_mean=1.0,
                samples=integration_sample_number,
                backend_options={"threshold": False, "postselect": 0},
            )
        )

        dims = samples.shape

        assert len(dims) == 2
        assert dims[0] == integration_sample_number
        assert dims[1] == len(adj)
        assert samples.dtype == "int"
        assert (samples >= 0).all()

    def test_threshold_nopostselect_integration(self, adj):
        """Integration test to check if function returns samples of correct form, i.e., correct
        number of samples, correct number of modes, all integers of zeros and ones """
        samples = np.array(
            sample.sample(
                A=adj,
                n_mean=1.0,
                samples=integration_sample_number,
                backend_options={"threshold": True, "postselect": 0},
            )
        )

        dims = samples.shape

        assert len(dims) == 2
        assert dims[0] == integration_sample_number
        assert dims[1] == len(adj)
        assert samples.dtype == "int"
        assert (samples >= 0).all()
        assert (samples <= 1).all()

    def test_pnr_postselect_integration(self, adj):
        """Integration test to check if function returns samples of correct form, i.e., correct
        number of samples, correct number of modes, all non-negative integers with total photon
        number not less than 1 """
        samples = np.array(
            sample.sample(
                A=adj,
                n_mean=1.0,
                samples=integration_sample_number,
                backend_options={"threshold": False, "postselect": 1},
            )
        )

        dims = samples.shape

        assert len(dims) == 2
        assert dims[0] == integration_sample_number
        assert dims[1] == len(adj)
        assert samples.dtype == "int"
        assert (samples >= 0).all()
        assert (np.sum(samples, axis=1) >= 1).all()

    def test_threshold_postselect_integration(self, adj):
        """Integration test to check if function returns samples of correct form, i.e., correct
        number of samples, correct number of modes, all integers of zeros and ones with total
        click number not less than 1 """
        samples = np.array(
            sample.sample(
                A=adj,
                n_mean=1.0,
                samples=integration_sample_number,
                backend_options={"threshold": True, "postselect": 1},
            )
        )

        dims = samples.shape

        assert len(dims) == 2
        assert dims[0] == integration_sample_number
        assert dims[1] == len(adj)
        assert samples.dtype == "int"
        assert (samples >= 0).all()
        assert (samples <= 1).all()
        assert (np.sum(samples, axis=1) >= 1).all()


# pylint: disable=expression-not-assigned,pointless-statement
class TestSampleSF:
    """Tests for the function ``strawberryfields.gbs.sample._sample_sf``"""

    def test_invalid_backend(self, monkeypatch):
        """Tests if function raises a ``ValueError`` when an invalid backend is selected"""

        invalid_backend = ""

        with pytest.raises(ValueError, match="Invalid backend selected"):
            sample._sample_sf(
                p=sf.Program(num_subsystems=1),
                shots=sample_number,
                backend_options={"remote": False, "backend": invalid_backend},
            )

    @pytest.mark.parametrize("valid_backend", sample.QUANTUM_BACKENDS)
    @pytest.mark.parametrize("dim", [4])
    def test_sample_sf_samples(self, dim, adj, valid_backend):
        """Tests if function returns samples of correct form, i.e., correct number of samples,
        correct number of modes, all non-negative integers"""

        p = sf.Program(dim)
        mean_photon_per_mode = 1.0

        with p.context as q:
            sf.ops.GraphEmbed(adj, mean_photon_per_mode=mean_photon_per_mode) | q
            sf.ops.Measure | q

        p = p.compile("gbs")

        samples = sample._sample_sf(
            p,
            shots=integration_sample_number,
            backend_options={"remote": False, "backend": valid_backend},
        )

        dims = samples.shape

        assert len(dims) == 2
        assert dims[0] == integration_sample_number
        assert dims[1] == len(adj)
        assert samples.dtype == "int"
        assert (samples >= 0).all()


class TestUniform:
    """Tests for the function ``strawberryfields.gbs.sample.uniform``"""

    def test_insufficient_modes(self):
        """Tests if function returns ``ValueError`` when user specifies a number of ``modes``
        less than 1 """
        with pytest.raises(ValueError, match="Modes and sampled_modes"):
            sample.uniform(modes=0, sampled_modes=2, samples=2)

    def test_insufficient_sampled_modes(self):
        """Tests if function returns ``ValueError`` when user specifies a number of
        ``sampled_modes`` less than 1 """
        with pytest.raises(ValueError, match="Modes and sampled_modes"):
            sample.uniform(modes=2, sampled_modes=0, samples=2)

    def test_sampled_modes_exceeds_modes(self):
        """Test if function returns ``ValueError`` when user specifies a number of
        ``sampled_modes`` that exceeds ``modes`` """
        with pytest.raises(ValueError, match="Modes and sampled_modes"):
            sample.uniform(modes=2, sampled_modes=3, samples=2)

    def test_insufficient_samples(self):
        """Test if function returns ``ValueError`` when user specifies a number of samples less
        than 1 """
        with pytest.raises(ValueError, match="Number of samples must be greater than zero"):
            sample.uniform(modes=2, sampled_modes=2, samples=0)

    def test_output_dimensions(self):
        """Tests if function returns list of correct dimensions"""
        samples = np.array(sample.uniform(modes=2, sampled_modes=1, samples=3))
        dims = samples.shape
        assert len(dims) == 2
        assert dims[0] == 3
        assert dims[1] == 2

    def test_output_sampled_modes(self):
        """Tests if samples from function are only zeros and ones and have a number of ones equal to
        ``sampled_modes``"""
        samples = np.array(sample.uniform(modes=2, sampled_modes=1, samples=3))

        only_zero_one = True

        for samp in samples:
            if not np.allclose(np.unique(samp), [0, 1]):
                only_zero_one = False

        assert only_zero_one
        assert np.unique(np.sum(samples, axis=1)) == 1


@pytest.mark.parametrize("dim", [4])
def test_seed(dim, adj):
    """Test for the function ``strawberryfields.gbs.sample.seed``. Checks that samples are identical
    after repeated initialization of ``seed``."""

    sample.seed(1968)
    q_s_1 = sample.sample(A=adj, n_mean=2, samples=10, backend_options={"threshold": False})
    u_s_1 = sample.uniform(modes=dim, sampled_modes=2, samples=10)

    sample.seed(1968)
    q_s_2 = sample.sample(A=adj, n_mean=2, samples=10, backend_options={"threshold": False})
    u_s_2 = sample.uniform(modes=dim, sampled_modes=2, samples=10)

    assert np.array_equal(q_s_1, q_s_2)
    assert np.array_equal(u_s_1, u_s_2)


@pytest.mark.parametrize("dim", [6])
def test_subgraphs_invalid_distribution(graph):
    """Tests if function ``sample.subgraphs`` raises a ``ValueError`` for an
    invalid sampling distribution"""
    with pytest.raises(ValueError, match="Invalid distribution selected"):
        sample.subgraphs(graph, nodes=2, samples=10, sample_options={"distribution": ""})


@pytest.mark.parametrize(
    "dim, nodes, samples", [(6, 4, integration_sample_number), (8, 4, integration_sample_number)]
)
@pytest.mark.parametrize("distribution", ("uniform", "gbs"))
def test_subgraphs_integration(graph, nodes, samples, distribution):
    """Integration tests for the function ``sample.subgraphs``"""

    graph = nx.relabel_nodes(graph, lambda x: x ** 2)
    graph_nodes = set(graph.nodes)
    output_samples = sample.subgraphs(
        graph=graph, nodes=nodes, samples=samples, sample_options={"distribution": distribution}
    )

    assert len(output_samples) == samples
    assert all(set(sample).issubset(graph_nodes) for sample in output_samples)


@pytest.mark.parametrize("dim", [6])
class TestToSubgraphs:
    """Tests for the function ``sample.to_subgraphs``"""

    quantum_samples = [
        [0, 1, 1, 1, 1, 1],
        [1, 0, 0, 1, 0, 0],
        [1, 1, 1, 1, 1, 1],
        [0, 0, 1, 0, 0, 1],
        [0, 1, 1, 1, 0, 0],
        [0, 0, 0, 0, 1, 1],
        [0, 0, 0, 0, 1, 1],
        [1, 1, 0, 1, 1, 1],
        [1, 0, 0, 1, 0, 0],
        [0, 0, 0, 0, 1, 1],
    ]

    subgraphs = [
        [1, 2, 3, 4, 5],
        [0, 3],
        [0, 1, 2, 3, 4, 5],
        [2, 5],
        [1, 2, 3],
        [4, 5],
        [4, 5],
        [0, 1, 3, 4, 5],
        [0, 3],
        [4, 5],
    ]

    def test_graph(self, graph):
        """Test if function returns correctly processed subgraphs given input samples of the list
        ``quantum_samples``."""
        assert sample.to_subgraphs(graph, samples=self.quantum_samples) == self.subgraphs

    def test_graph_mapped(self, graph):
        """Test if function returns correctly processed subgraphs given input samples of the list
        ``quantum_samples``. Note that graph nodes are numbered in this test as [0, 1, 4, 9,
        ...] (i.e., squares of the usual list) as a simple mapping to explore that the optimised
        subgraph returned is still a valid subgraph."""
        graph = nx.relabel_nodes(graph, lambda x: x ** 2)
        graph_nodes = list(graph.nodes)
        subgraphs_mapped = [
            sorted([graph_nodes[i] for i in subgraph]) for subgraph in self.subgraphs
        ]

        assert sample.to_subgraphs(graph, samples=self.quantum_samples) == subgraphs_mapped


def test_modes_from_counts():
    """Test if the function ``strawberryfields.gbs.sample.modes_from_counts`` returns the correct
    mode samples when input a set of photon count samples."""

    counts = [[0, 0, 0, 0], [1, 0, 0, 2], [1, 1, 1, 0], [1, 2, 1, 0], [0, 1, 0, 2, 4]]

    modes = [[], [0, 3, 3], [0, 1, 2], [0, 1, 1, 2], [1, 3, 3, 4, 4, 4, 4]]

    assert [sample.modes_from_counts(s) for s in counts] == modes