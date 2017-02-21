from __future__ import print_function
import numpy as np
import scipy.sparse as sp
from scipy.constants import pi

from discretize import utils
from discretize.TensorMesh import BaseTensorMesh, BaseRectangularMesh
from discretize.InnerProducts import InnerProducts
from discretize.View import CylView


class CylMesh(BaseTensorMesh, BaseRectangularMesh, InnerProducts, CylView):
    """
        CylMesh is a mesh class for cylindrical problems

        .. note::

            for a cylindrically symmetric mesh use [hx, 1, hz]

        ::

            cs, nc, npad = 20., 30, 8
            hx = utils.meshTensor([(cs,npad+10,-0.7), (cs,nc), (cs,npad,1.3)])
            hz = utils.meshTensor([(cs,npad   ,-1.3), (cs,nc), (cs,npad,1.3)])
            mesh = Mesh.CylMesh([hx,1,hz], [0.,0,-hz.sum()/2.])
    """

    _meshType = 'CYL'

    _unitDimensions = [1, 2*np.pi, 1]

    def __init__(self, h, x0=None, cartesianOrigin=None):
        BaseTensorMesh.__init__(self, h, x0)
        assert np.abs(self.hy.sum() - 2*np.pi) < 1e-10, "The 2nd dimension must sum to 2*pi"
        if self.dim == 2:
            print('Warning, a disk mesh has not been tested thoroughly.')
        cartesianOrigin = (np.zeros(self.dim) if cartesianOrigin is None
                           else cartesianOrigin)
        assert len(cartesianOrigin) == self.dim, ("cartesianOrigin must be the "
                                                  "same length as the dimension"
                                                  " of the mesh.")
        self.cartesianOrigin = np.array(cartesianOrigin, dtype=float)

    @property
    def isSymmetric(self):
        return self.nCy == 1

    @property
    def nNx(self):
        """
        Number of nodes in the x-direction

        :rtype: int
        :return: nNx
        """
        if self.isSymmetric is True:
            return self.nCx
        return self.nCx + 1

    @property
    def nNy(self):
        """
        Number of nodes in the y-direction

        :rtype: int
        :return: nNy
        """
        if self.isSymmetric is True:
            return 0
        return self.nCy

    @property
    def vnFx(self):
        """
        Number of x-faces in each direction

        :rtype: numpy.array
        :return: vnFx, (dim, )
        """
        return self.vnC

    @property
    def vnEy(self):
        """
        Number of y-edges in each direction

        :rtype: numpy.array
        :return: vnEy or None if dim < 2, (dim, )
        """
        nNx = self.nNx if self.isSymmetric else self.nNx - 1
        return np.r_[nNx, self.nCy, self.nNz]

    @property
    def vnEz(self):
        """
        Number of z-edges in each direction

        :rtype: numpy.array
        :return: vnEz or None if nCy > 1, (dim, )
        """
        if self.isSymmetric is True:
            return np.r_[self.nNx, self.nNy, self.nCz]
        else:
            return None

    @property
    def nEz(self):
        """
        Number of z-edges

        :rtype: int
        :return: nEz
        """
        if self.isSymmetric is True:
            return self.vnEz.prod()
        return (np.r_[self.nNx-1, self.nNy, self.nCz]).prod() + self.nCz

    @property
    def vectorCCx(self):
        """Cell-centered grid vector (1D) in the x direction."""
        return np.r_[0, self.hx[:-1].cumsum()] + self.hx*0.5

    @property
    def vectorCCy(self):
        """Cell-centered grid vector (1D) in the y direction."""
        if self.isSymmetric is True:
            return np.r_[0, self.hy[:-1]]
        return np.r_[0, self.hy[:-1].cumsum()] + self.hy*0.5

    @property
    def vectorNx(self):
        """Nodal grid vector (1D) in the x direction."""
        if self.isSymmetric is True:
            return self.hx.cumsum()
        return np.r_[0, self.hx].cumsum()

    @property
    def vectorNy(self):
        """Nodal grid vector (1D) in the y direction."""
        if self.isSymmetric is True:
            # There aren't really any nodes, but all the grids need
            # somewhere to live, why not zero?!
            return np.r_[0]
        return np.r_[0, self.hy[:-1].cumsum()]

    @property
    def vectorNz(self):
        return np.r_[0, self.hz].cumsum()

    @property
    def edge(self):
        """Edge lengths"""
        if getattr(self, '_edge', None) is None:
            if self.isSymmetric is True:
                self._edge = 2*pi*self.gridN[:, 0]
            else:
                edgeR = np.kron(
                    np.ones(self.vnC[2]+1),
                    np.kron(np.ones(self.vnC[1]), self.hx)
                )
                edgeT = np.kron(
                    np.ones(self.vnC[2]+1),
                    np.kron(self.hy, self.vectorNx[1:])
                )
                edgeZ = np.kron(
                    self.hz, np.ones(self.vnC[:2].prod()+1)
                )
                self._edge = np.hstack([edgeR, edgeT, edgeZ])
        return self._edge

    @property
    def area(self):
        """Face areas"""
        if getattr(self, '_area', None) is None:
            if self.isSymmetric is True:
                areaR = np.kron(self.hz, 2*pi*self.vectorNx)
                areaZ = np.kron(
                    np.ones_like(self.vectorNz), pi*(self.vectorNx**2 -
                    np.r_[0, self.vectorNx[:-1]]**2)
                )
                self._area = np.r_[areaR, areaZ]
            else:
                areaR = np.kron(self.hz, np.kron(self.hy, self.vectorNx[1:]))
                areaT = np.kron(self.hz, np.kron(np.ones(self.nNy), self.hx))
                areaZ = np.kron(
                    np.ones(self.nNz), np.kron(
                        self.hy,
                        0.5 * (self.vectorNx[1:]**2 - self.vectorNx[:-1]**2)
                    )
                )
                self._area = np.r_[areaR, areaT, areaZ]
        return self._area

    @property
    def vol(self):
        """Volume of each cell"""
        if getattr(self, '_vol', None) is None:
            if self.isSymmetric is True:
                az = pi*(self.vectorNx**2 - np.r_[0, self.vectorNx[:-1]]**2)
                self._vol = np.kron(self.hz, az)
            else:
                self._vol = np.kron(
                    self.hz, np.kron(
                        self.hy,
                        0.5 * (self.vectorNx[1:]**2 - self.vectorNx[:-1]**2)
                    )
                )
        return self._vol

    ####################################################
    # Grids
    ####################################################

    @property
    def gridFx(self):
        if getattr(self, '_gridFx', None) is None:
            if self.isSymmetric is True:
                return super(CylMesh, self).gridFx
            else:
                self._gridFx = utils.ndgrid([
                    self.vectorNx[1:], self.vectorCCy, self.vectorCCz
                ])
        return self._gridFx

    @property
    def gridFy(self):
        if getattr(self, '_gridFy', None) is None:
            if self.isSymmetric is True:
                return super(CylMesh, self).gridFy
            else:
                self._gridFy = utils.ndgrid([
                    self.vectorCCx, self.vectorNy, self.vectorCCz
                ])
        return self._gridFy

    @property
    def gridEy(self):
        if getattr(self, '_gridEy', None) is None:
            if self.isSymmetric is True:
                return super(CylMesh, self).gridEy
            else:
                self._gridEy = utils.ndgrid([
                    self.vectorNx[1:], self.vectorCCy, self.vectorNz
                ])
        return self._gridEy

    @property
    def gridEz(self):
        if getattr(self, '_gridEz', None) is None:
            if self.isSymmetric is True:
                return super(CylMesh, self).gridEz
            else:
                gridEz = super(CylMesh, self).gridEz

                self._gridEz = self._deflationMatrix('Ez') * gridEz
        return self._gridEz


    ####################################################
    # Operators
    ####################################################

    @property
    def faceDiv(self):
        """Construct divergence operator (face-stg to cell-centres)."""
        if getattr(self, '_faceDiv', None) is None:
            n = self.vnC
            # Compute faceDivergence operator on faces
            D1 = self.faceDivx
            D3 = self.faceDivz
            if self.isSymmetric is True:
                D = sp.hstack((D1, D3), format="csr")
            elif self.nCy > 1:
                D2 = self.faceDivy
                D = sp.hstack((D1, D2, D3), format="csr")
            self._faceDiv = D
        return self._faceDiv

    @property
    def faceDivx(self):
        """
        Construct divergence operator in the x component
        (face-stg to cell-centres).
        """
        if getattr(self, '_faceDivx', None) is None:
            D1 = utils.kron3(
                utils.speye(self.nCz),
                utils.speye(self.nCy),
                utils.ddx(self.nCx)
            ) * self._deflationMatrix('Fx')
            S = self.r(self.area, 'F', 'Fx', 'V')
            V = self.vol
            self._faceDivx = utils.sdiag(1/V)*D1*utils.sdiag(S)
        return self._faceDivx

    @property
    def faceDivy(self):
        """
        Construct divergence operator in the y component
        (face-stg to cell-centres).
        """
        # raise NotImplementedError(
        if getattr(self, '_faceDivy', None) is None:
            # TODO: this needs to wrap to join up faces which are
            # connected in the cylinder
            D2 = utils.kron3(
                utils.speye(self.nCz),
                utils.ddx(self.nCy),
                utils.speye(self.nCx)
            ) * self._deflationMatrix('Fy')
            S = self.r(self.area, 'F', 'Fy', 'V')
            V = self.vol
            self._faceDivy = utils.sdiag(1/V)*D2*utils.sdiag(S)
        return self._faceDivy

    @property
    def faceDivz(self):
        """
        Construct divergence operator in the z component
        (face-stg to cell-centres).
        """
        if getattr(self, '_faceDivz', None) is None:
            D3 = utils.kron3(
                utils.ddx(self.nCz),
                utils.speye(self.nCy),
                utils.speye(self.nCx)
            )
            S = self.r(self.area, 'F', 'Fz', 'V')
            V = self.vol
            self._faceDivz = utils.sdiag(1/V)*D3*utils.sdiag(S)
        return self._faceDivz

    @property
    def cellGrad(self):
        """The cell centered Gradient, takes you to cell faces."""
        raise NotImplementedError('Cell Grad is not yet implemented.')

    @property
    def nodalGrad(self):
        """Construct gradient operator (nodes to edges)."""
        # Nodal grad does not make sense for cylindrically symmetric mesh.
        if self.isSymmetric is True:
            return None
        raise NotImplementedError('nodalGrad not yet implemented')

    @property
    def nodalLaplacian(self):
        """Construct laplacian operator (nodes to edges)."""
        raise NotImplementedError('nodalLaplacian not yet implemented')

    @property
    def edgeCurl(self):
        """The edgeCurl property."""
        # if self.nCy > 1:
        #     raise NotImplementedError(
        #         'Edge curl not yet implemented for nCy > 1')
        if getattr(self, '_edgeCurl', None) is None:
            A = self.area
            E = self.edge

            if self.isSymmetric is True:
            # 1D Difference matricies
                dr = sp.spdiags(
                    (np.ones((self.nCx+1, 1))*[-1, 1]).T, [-1, 0],
                    self.nCx, self.nCx, format="csr"
                )
                dz = sp.spdiags(
                    (np.ones((self.nCz+1, 1))*[-1, 1]).T, [0, 1],
                    self.nCz, self.nCz+1, format="csr"
                )
                # 2D Difference matricies
                Dr = sp.kron(sp.identity(self.nNz), dr)
                Dz = -sp.kron(dz, sp.identity(self.nCx))

                # Edge curl operator
                self._edgeCurl = (
                    utils.sdiag(1/A)*sp.vstack((Dz, Dr)) * utils.sdiag(E)
                )
            else:
                ### Curl that lands on R-faces ###
                # Theta contribution
                Dt_r = utils.kron3(
                    utils.ddx(self.nCz),
                    utils.speye(self.nCy),
                    utils.speye(self.nCx)
                )
                ddxz = utils.ddx(self.nCy)[:,:-1] + sp.csr_matrix((np.r_[1.], (np.r_[self.nCy-1], np.r_[0])), shape=(self.nCy, self.nCy))
                # ddxz = sp.hstack([utils.spzeros(self.nCy, 1), ddxz])

                Dz_r = sp.kron(ddxz, utils.speye(self.nCx))
                Dz_r = sp.hstack([utils.spzeros(self.vnC[:2].prod(), 1), Dz_r])
                Dz_r = sp.kron(utils.speye(self.nCz), Dz_r)

                # Z contribution
                # Dz_r = sp.hstack([utils.spzeros(self.vnF[1], 1), ddxz])

                # Zeros of the right size
                O1 = utils.spzeros(self.nFx, self.nEx)

                # R-contribution to Curl
                Cr = sp.hstack((O1, -Dt_r, Dz_r))

                ### Curl that lands on T-faces ###
                # contribution from R
                Dr_t = utils.kron3(utils.ddx(self.nCz), utils.speye(self.nCy), utils.speye(self.nCx))

                # Zeros of the right size
                O2 = utils.spzeros(self.nFy, self.nEy)

                # contribution from Z
                ddxr = utils.ddx(self.nCx)
                Ddxr = sp.kron(utils.speye(self.nCy), ddxr[:,1:])
                wrap_z = sp.csr_matrix((-1*np.ones(self.nCy), (np.arange(0, self.vnC[:2].prod(), step=self.vnC[0]), np.zeros(self.nCy))), shape=(self.vnC[:2].prod(), 1))
                Dz_t = sp.kron(utils.speye(self.nCz), sp.hstack([wrap_z, Ddxr]))

                # T-contribution to the Curl
                Ct = sp.hstack((Dr_t, O2, -Dz_t))

                ### Curl that lands on the Z-faces ###
                # contribution from R
                ddxz = utils.ddx(self.nCy)[:,:-1] + sp.csr_matrix((np.r_[1.], (np.r_[self.nCy-1], np.r_[0])), shape=(self.nCy, self.nCy))
                Dr_z = utils.kron3(utils.speye(self.nCz+1), ddxz, utils.speye(self.nCx))
                # = sp.kron(utils.speye(self.nCz+1), ddxz)

                # contribution from T
                ddxt = utils.ddx(self.nCx)[:,1:]
                Dt_z = utils.kron3(
                    utils.speye(self.nCz+1), utils.speye(self.nCy), ddxt
                )

                # Zeros of the right size
                O3 = utils.spzeros(self.nFz, self.nEz)

                # Z contribution to the curl
                Cz = sp.hstack((-Dr_z, Dt_z, O3))

                self._edgeCurl = (
                    utils.sdiag(1/A) *
                    sp.vstack([Cr, Ct, Cz], format="csr") *
                    utils.sdiag(E)
                )

        return self._edgeCurl

    @property
    def aveE2CC(self):
        "Construct the averaging operator on cell edges to cell centers."
        if getattr(self, '_aveE2CC', None) is None:
            # The number of cell centers in each direction
            n = self.vnC
            if self.isSymmetric is True:
                avR = utils.av(n[0])[:, 1:]
                avR[0, 0] = 1.
                self._aveE2CC = sp.kron(utils.av(n[2]), avR, format="csr")
            else:
                raise NotImplementedError(
                    'wrapping in the averaging is not yet implemented'
                )
                # self._aveE2CC = (1./3)*sp.hstack((utils.kron3(utils.av(n[2]),
                #                                               utils.av(n[1]),
                #                                               utils.speye(n[0])),
                #                                   utils.kron3(utils.av(n[2]),
                #                                               utils.speye(n[1]),
                #                                               utils.av(n[0])),
                #                                   utils.kron3(utils.speye(n[2]),
                #                                               utils.av(n[1]),
                #                                               utils.av(n[0]))),
                #                                  format="csr")
        return self._aveE2CC

    @property
    def aveE2CCV(self):
        "Construct the averaging operator on cell edges to cell centers."
        if getattr(self, '_aveE2CCV', None) is None:
            # The number of cell centers in each direction
            n = self.vnC
            if self.isSymmetric is True:
                return self.aveE2CC
            else:
                raise NotImplementedError('wrapping in the averaging is not '
                                          'yet implemented')
        return self._aveE2CCV

    @property
    def aveF2CC(self):
        "Construct the averaging operator on cell faces to cell centers."
        if getattr(self, '_aveF2CC', None) is None:
            n = self.vnC
            if self.isSymmetric is True:
                avR = utils.av(n[0])[:, 1:]
                avR[0, 0] = 1.
                self._aveF2CC = ((0.5)*sp.hstack((sp.kron(utils.speye(n[2]),
                                                          avR),
                                                  sp.kron(utils.av(n[2]),
                                                          utils.speye(n[0]))),
                                                 format="csr"))
            else:
                raise NotImplementedError('wrapping in the averaging is not '
                                          'yet implemented')
                # self._aveF2CC = (1./3.)*sp.hstack((utils.kron3(utils.speye(n[2]),
                #                                                utils.speye(n[1]),
                #                                                utils.av(n[0])),
                #                                    utils.kron3(utils.speye(n[2]),
                #                                                utils.av(n[1]),
                #                                                utils.speye(n[0])),
                #                                    utils.kron3(utils.av(n[2]),
                #                                                utils.speye(n[1]),
                #                                                utils.speye(n[0]))),
                #                                   format="csr")
        return self._aveF2CC

    @property
    def aveF2CCV(self):
        "Construct the averaging operator on cell faces to cell centers."
        if getattr(self, '_aveF2CCV', None) is None:
            n = self.vnC
            if self.isSymmetric is True:
                avR = utils.av(n[0])[:, 1:]
                avR[0, 0] = 1.
                self._aveF2CCV = sp.block_diag((sp.kron(utils.speye(n[2]),
                                                        avR),
                                                sp.kron(utils.av(n[2]),
                                                        utils.speye(n[0]))),
                                               format="csr")
            else:
                raise NotImplementedError('wrapping in the averaging is not '
                                          'yet implemented')
        return self._aveF2CCV


    ####################################################
    # Deflation Matrices
    ####################################################

    def _deflationMatrix(self, location):
        assert(
            location in ['N','F','Fx','Fy','E','Ex','Ey'] + (
                ['Fz','Ez'] if self.dim == 3 else []
            )
        )

        wrap_theta = sp.csr_matrix(
            (
                [1]*(self.vnC[1] + 1),
                (np.arange(0, self.vnC[1]+1), np.hstack((np.arange(0, self.vnC[1]), [0])) )
            ),
            shape=(self.vnC[1]+1, self.vnC[1])
        )

        collapse_x = sp.csr_matrix(
            (
                [1]*self.vnC[0],
                (np.arange(1, self.vnC[0]+1), np.arange(0, self.vnC[0]))), shape=(self.vnC[0]+1, self.vnC[0])
        )

        if location in ['E', 'F']:
            pass

        if location == 'Fx':
            return utils.kron3(
                utils.speye(self.vnC[2]), utils.speye(self.vnC[1]), collapse_x
            )

        elif location == 'Fy':
            return utils.kron3(
                utils.speye(self.vnC[2]),
                wrap_theta,
                utils.speye(self.vnC[0])
            )
        elif location == 'Fz':
            return utils.speye(self.vnF[2])

        elif location == 'Ex':
            pass

        elif location == 'Ey':
            pass

        elif location == 'Ez':
            removeme = np.arange(self.vnN[0], self.vnN[:2].prod(), step=self.vnN[0])
            keepme = np.ones(self.vnN[:2].prod(), dtype=bool)
            keepme[removeme] = False

            eye = sp.eye(self.vnN[:2].prod())
            eye = eye.tocsr()[keepme, :]
            return sp.kron(utils.speye(self.nCz), eye)


    ####################################################
    # Interpolation
    ####################################################

    def getInterpolationMat(self, loc, locType='CC', zerosOutside=False):
        """ Produces interpolation matrix

        :param numpy.ndarray loc: Location of points to interpolate to
        :param str locType: What to interpolate (see below)
        :rtype: scipy.sparse.csr_matrix
        :return: M, the interpolation matrix

        locType can be::

            'Ex'    -> x-component of field defined on edges
            'Ey'    -> y-component of field defined on edges
            'Ez'    -> z-component of field defined on edges
            'Fx'    -> x-component of field defined on faces
            'Fy'    -> y-component of field defined on faces
            'Fz'    -> z-component of field defined on faces
            'N'     -> scalar field defined on nodes
            'CC'    -> scalar field defined on cell centers
            'CCVx'  -> x-component of vector field defined on cell centers
            'CCVy'  -> y-component of vector field defined on cell centers
            'CCVz'  -> z-component of vector field defined on cell centers
        """
        if self.isSymmetric and locType in ['Ex', 'Ez', 'Fy']:
            raise Exception(
                "Symmetric CylMesh does not support {0!s} interpolation, "
                "as this variable does not exist.".format(locType)
            )

        if locType in ['CCVx', 'CCVy', 'CCVz']:
            Q = utils.interpmat(loc, *self.getTensor('CC'))
            Z = utils.spzeros(loc.shape[0], self.nC)
            if locType == 'CCVx':
                Q = sp.hstack([Q, Z])
            elif locType == 'CCVy':
                Q = sp.hstack([Q])
            elif locType == 'CCVz':
                Q = sp.hstack([Z, Q])

            if zerosOutside:
                Q[indZeros, :] = 0

            return Q.tocsr()

        return self._getInterpolationMat(loc, locType, zerosOutside)

    def getInterpolationMatCartMesh(self, Mrect, locType='CC', locTypeTo=None):
        """
            Takes a cartesian mesh and returns a projection to translate onto
            the cartesian grid.
        """

        assert self.isSymmetric, (
            "Currently we have not taken into account other projections for "
            "more complicated CylMeshes"
        )

        if locTypeTo is None:
            locTypeTo = locType

        if locType == 'F':
            # do this three times for each component
            X = self.getInterpolationMatCartMesh(
                Mrect, locType='Fx', locTypeTo=locTypeTo+'x'
            )
            Y = self.getInterpolationMatCartMesh(
                Mrect, locType='Fy', locTypeTo=locTypeTo+'y'
            )
            Z = self.getInterpolationMatCartMesh(
                Mrect, locType='Fz', locTypeTo=locTypeTo+'z'
            )
            return sp.vstack((X, Y, Z))
        if locType == 'E':
            X = self.getInterpolationMatCartMesh(
                Mrect, locType='Ex', locTypeTo=locTypeTo+'x'
            )
            Y = self.getInterpolationMatCartMesh(
                Mrect, locType='Ey', locTypeTo=locTypeTo+'y'
            )
            Z = utils.spzeros(getattr(Mrect, 'n' + locTypeTo + 'z'), self.nE)
            return sp.vstack((X, Y, Z))

        grid = getattr(Mrect, 'grid' + locTypeTo)
        # This is unit circle stuff, 0 to 2*pi, starting at x-axis, rotating
        # counter clockwise in an x-y slice
        theta = - np.arctan2(
            grid[:, 0] - self.cartesianOrigin[0], grid[:, 1] -
            self.cartesianOrigin[1]
        ) + np.pi/2
        theta[theta < 0] += np.pi*2.0
        r = ((grid[:, 0] - self.cartesianOrigin[0])**2 + (grid[:, 1] -
             self.cartesianOrigin[1])**2)**0.5

        if locType in ['CC', 'N', 'Fz', 'Ez']:
            G, proj = np.c_[r, theta, grid[:, 2]], np.ones(r.size)
        else:
            dotMe = {
                'Fx': Mrect.normals[:Mrect.nFx, :],
                'Fy': Mrect.normals[Mrect.nFx:(Mrect.nFx + Mrect.nFy), :],
                'Fz': Mrect.normals[-Mrect.nFz:, :],
                'Ex': Mrect.tangents[:Mrect.nEx, :],
                'Ey': Mrect.tangents[Mrect.nEx:(Mrect.nEx+Mrect.nEy), :],
                'Ez': Mrect.tangents[-Mrect.nEz:, :],
            }[locTypeTo]
            if 'F' in locType:
                normals = np.c_[
                    np.cos(theta), np.sin(theta), np.zeros(theta.size)
                ]
                proj = (normals * dotMe).sum(axis=1)
            if 'E' in locType:
                tangents = np.c_[
                    -np.sin(theta), np.cos(theta), np.zeros(theta.size)
                ]
                proj = (tangents * dotMe).sum(axis=1)
            G = np.c_[r, theta, grid[:, 2]]

        interpType = locType
        if interpType == 'Fy':
            interpType = 'Fx'
        elif interpType == 'Ex':
            interpType = 'Ey'

        Pc2r = self.getInterpolationMat(G, interpType)
        Proj = utils.sdiag(proj)
        return Proj * Pc2r
