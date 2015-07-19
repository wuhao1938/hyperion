import os
import sys
from copy import deepcopy

import h5py
import numpy as np
from astropy.tests.helper import pytest

from ...util.functions import random_id
from ...model import Model
from ...model.tests.test_helpers import get_realistic_test_dust

from .. import CartesianGrid, \
               SphericalPolarGrid, \
               CylindricalPolarGrid, \
               AMRGrid, \
               OctreeGrid

DATA = os.path.join(os.path.dirname(__file__), 'data')

ALL_GRID_TYPES = ['car', 'amr', 'oct']

PY27 = sys.version_info[:2] == (2, 7)

@pytest.mark.skipif("not PY27")
class TestToYt(object):

    def setup_method(self, method):

        # Set up grids
        self.grid = {}

        self.grid['car'] = CartesianGrid([-1., 1.],
                                         [-2., 0., 2.],
                                         [-3., -1., 1., 3.])
        self.grid['cyl'] = CylindricalPolarGrid([0., 1.],
                                                [-1., 0., 1.],
                                                [0., 0.75 * np.pi, 1.25 * np.pi, 2. * np.pi])
        self.grid['sph'] = SphericalPolarGrid([0., 0.5, 1.],
                                              [0., np.pi],
                                              [0., 0.75 * np.pi, 1.25 * np.pi, 2. * np.pi])

        self.grid['amr'] = AMRGrid()
        level = self.grid['amr'].add_level()
        grid = level.add_grid()
        grid.xmin, grid.xmax = -1., 1.
        grid.ymin, grid.ymax = -1., 1.
        grid.zmin, grid.zmax = -1., 1.
        grid.nx, grid.ny, grid.nz = 8, 6, 4

        refined = [1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                   0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
        self.grid['oct'] = OctreeGrid(0., 0., 0., 10., 10., 10.,
                                      np.array(refined).astype(bool))

        # Set up initial densities
        self.density = {}
        self.density['car'] = np.ones((3, 2, 1))
        self.density['cyl'] = np.ones((3, 2, 1))
        self.density['sph'] = np.ones((3, 1, 2))
        amr_q = deepcopy(self.grid['amr'])
        amr_q.levels[0].grids[0].quantities['density'] = np.ones((4, 6, 8))
        self.density['amr'] = amr_q['density']
        self.density['oct'] = np.ones(len(refined))

    @pytest.mark.parametrize(('grid_type'), ALL_GRID_TYPES)
    def test_to_yt(self, tmpdir, grid_type):

        from yt.mods import ProjectionPlot

        g = self.grid[grid_type]
        g['density'] = []
        g['density'].append(self.density[grid_type])
        pf = g.to_yt()

        p = ProjectionPlot(pf, 'x', ["density"], center='c', origin='native')
        p.save(tmpdir.join('test.png').strpath)


@pytest.mark.skipif("not PY27")
def test_from_yt(tmpdir):

    from yt import load
    ds = load(os.path.join(DATA, 'DD0010', 'moving7_0010'))

    def _dust_density(field, data):
        return data["density"].in_units('g/cm**3') * 0.01

    ds.add_field("dust_density", function=_dust_density, units='g/cm**3')

    amr = AMRGrid.from_yt(ds, quantity_mapping={'density':'dust_density'}, center_origin=True)

    m = Model()

    m.set_amr_grid(amr)

    m.add_density_grid(amr['density'], get_realistic_test_dust())

    s = m.add_point_source()
    s.luminosity = 1000
    s.temperature = 1000

    m.set_n_initial_iterations(3)

    m.set_n_photons(initial=1e5, imaging=0)

    m.set_propagation_check_frequency(1)

    m.set_copy_input(False)

    input_file = tmpdir.join('test.rtin').strpath
    output_file = tmpdir.join('test.rtout').strpath

    m.write(input_file)
    m.run(output_file)
