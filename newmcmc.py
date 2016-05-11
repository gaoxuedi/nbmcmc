from math import *
import numpy as np
import numpy.ma as ma
import sympy.mpmath as sy
import scipy.misc as fac
import scipy.special as sp
import scipy.spatial.distance as scd
import pymc
import matplotlib.pyplot as plt
plt.style.use('ggplot')


def sph_law_of_cos(u, v):
    '''Returns distance between two geographic
    coordinates in meters using spherical law of cosine'''
    R = 6371000
    u = np.radians(u)
    v = np.radians(v)
    delta_lon = v[1] - u[1]
    d = acos(sin(u[0]) * sin(v[0]) +
             cos(u[0]) * cos(v[0]) * cos(delta_lon)) * R
    return d


def ibd_count(m1, m2):
    count = 0
    for i in m1:
        if i == 0:
            continue
        for j in m2:
            if j == 0:
                continue
            if i == j:
                count += 1
    return count


def tot_count(m1, m2):
    total = 0
    for i in m1:
        if i == 0:
            continue
        for j in m2:
            if j == 0:
                continue
            total += 1
    return total


def tile_reshape(v, n, m):
    return np.tile(v, n).reshape(n, m)

# def equirect(u, v):
#    '''Returns distance between two geographic coordinates
#    in meters using equirectangular approximation'''
#    R = 6371000
#    u = np.radians(u)
#    v = np.radians(v)
#    delta_lon = v[1] - u[1]
#    delta_lat = v[0] - u[0]
#    x = delta_lon * cos((u[0] + v[0]) / 2.0)
#    y = delta_lat
#    d = sqrt(x * x + y * y) * R
#    return d


class NbMC:

    def __init__(self, mu, nb_start, density_start,
                 data_file, path="./", cartesian=True):
        self.mu = mu
        self.data_file = data_file
        self.path = path
        self.mu2 = -2.0 * self.mu
        self.z = exp(self.mu2)
        self.sqrz = sqrt(1.0 - self.z)
        self.g0 = log(1 / float(self.sqrz))
        self.nb_start = nb_start
        self.d_start = density_start
        self.taylor_terms = None
        self.t2 = None
        self.n_markers = None
        self.marker_names = None
        self.dist = None
        self.sz = None
        self.ibd = None
        self.tsz = None
        self.fbar = None
        self.fbar_1 = None
        self.weight = None

        self.parse_data(data_file, path, cartesian)
        self.set_taylor_terms()
        self.nb_prior_mu = None
        self.nb_prior_tau = None
        self.d_prior_mu = None
        self.d_prior_tau = None

    def set_prior_params(self, n_mu, n_tau, d_mu, d_tau):
        self.nb_prior_mu = n_mu
        self.nb_prior_tau = n_tau
        self.d_prior_mu = d_mu
        self.d_prior_tau = d_tau

    def parse_data(self, data_file, path, cartesian):
        data = np.array(np.genfromtxt(path + data_file,
                                      delimiter=",",
                                      dtype=str,
                                      skip_header=False,
                                      comments="#"))
        self.marker_names = data[0][3:]
        self.n_markers = len(self.marker_names)
        data = data[1:][:].T
        coords = np.array(data[:][1:3].T, dtype=float)
        if cartesian:
            self.dist = scd.pdist(coords, 'euclidean')
        else:
            self.dist = scd.pdist(coords, sph_law_of_cos)
        markers = np.array(data[:][3:], ndmin=2)
        markers = np.array(
            np.core.defchararray.split(markers, sep="/").tolist(), dtype=str)
        markers = np.core.defchararray.lower(markers)
        # order matters "na" needs to be after "nan"
        for n in ["none", "nan", "na", "x", "-", "."]:
            markers = np.core.defchararray.replace(markers, n, "0")
        markers = markers.astype(int, copy=False)
        self.ibd = np.array([scd.pdist(i, ibd_count) for i in markers],
                            dtype=int)
        self.sz = np.array([scd.pdist(i, tot_count) for i in markers],
                           dtype=int)
        self.tsz = np.sum(self.sz, axis=1, dtype=float)
        self.fbar = np.divide(np.sum(self.ibd, axis=1), self.tsz)
        self.fbar_1 = 1 - self.fbar
        self.weight = 2 / (self.tsz - 1.0)

    def set_taylor_terms(self):
        terms = 34
        n = len(self.dist)
        t = np.array([i for i in xrange(terms)])
        Li = tile_reshape(np.array([sy.polylog(i + 1, self.z)
                                   for i in xrange(terms)]), n, terms)
        fac2 = tile_reshape(fac.factorial(2*t), n, terms)
        two2t = tile_reshape(2**(t+1), n, terms)
        sign = tile_reshape((-1)**t, n, terms)
        self.t2 = tile_reshape(2*t, n, terms)
        dist = np.repeat(self.dist, terms).reshape(n, terms)
        x2t = np.power(dist, self.t2)
        num = np.multiply(Li, x2t)
        num = np.multiply(num, sign)
        den = np.multiply(fac2, two2t)
        self.taylor_terms = np.divide(num, den)

    def t_series(self, mask, sigma):
        a = np.power(float(sigma), self.t2)
        b = np.divide(1, a)
        c = np.multiply(b, self.taylor_terms)
        d = np.sum(c,axis=1)
        return ma.array(d,mask=mask)

    def bessel(self, x, sigma):
        t = (x / float(sigma)) * self.sqrz
        return sp.k0(t)

    def make_null_model(self, data=None):
        nb = pymc.Lognormal('nb', value=self.nb_start,
                            mu=self.nb_prior_mu,
                            tau=self.nb_prior_tau)
        density = pymc.Lognormal('density', value=self.d_start,
                                 mu=self.d_prior_mu,
                                 tau=self.d_prior_tau)

        @pymc.deterministic
        def sigma(nb=nb, d=density):
            return sqrt(nb / float(d))

        @pymc.deterministic
        def ss(s=sigma):
            return s * s

        @pymc.deterministic
        def neigh(nb=nb):
            return 4.0 * nb * pi


        @pymc.deterministic(plot=False)
        def Phi():
            pIBD = np.repeat(self.fbar,
                             self.ibd.shape[1]).reshape(self.ibd.shape)
            pIBD = ma.masked_less(pIBD,0).filled(0)
            return pIBD

        @pymc.stochastic(observed=True)
        def marginal_bin(value=self.ibd, p=Phi, n=self.sz):
            print p.shape, n.shape, value.shape
            return np.sum((value * np.log(p) + (n-value) *
                           np.log(1-p)).T * self.weight)

        Lsim = pymc.Container([[pymc.Binomial('Lsim_{}_{}'.format(i, j),
                                              n=self.sz[i][j],
                                              p=Phi[i][j]) for j
                                in xrange(self.ibd.shape[1])]
                               for i in xrange(self.ibd.shape[0])])
        return locals()

    def make_model(self):
        nb = pymc.Lognormal('nb', value=self.nb_start,
                            mu=self.nb_prior_mu,
                            tau=self.nb_prior_tau)
        density = pymc.Lognormal('density', value=self.d_start,
                                 mu=self.d_prior_mu,
                                 tau=self.d_prior_tau)

        @pymc.deterministic
        def sigma(nb=nb, d=density):
            return sqrt(nb / float(d))

        @pymc.deterministic
        def ss(s=sigma):
            return s * s

        @pymc.deterministic
        def neigh(nb=nb):
            return 4.0 * nb * pi

        # deterministic function to calculate pIBD from Wright Malecot formula
        @pymc.deterministic(plot=False, trace=False)
        def Phi(nb=nb, s=sigma):
            denom = 4.0 * pi * nb + self.g0
            use_bessel = ma.masked_less_equal(self.dist, 5 * s, copy=True)
            use_bessel = self.bessel(use_bessel, s)
            use_taylor = self.t_series(use_bessel.mask, s)
            phi = use_bessel.filled(use_taylor)
            phi = np.divide(phi, denom)
            phi_bar = np.multiply(self.sz, phi) # Check this!!!!
            phi_bar = np.sum(phi_bar, axis=1)  # and this
            phi_bar = np.divide(phi_bar, self.tsz)
            phi = tile_reshape(phi,self.n_markers,len(self.dist))
            r = (phi.T - phi_bar) / (1 - phi_bar)
            pIBD = ma.masked_less((self.fbar + self.fbar_1 * r), 0)
            # Change any negative values to zero
            pIBD = pIBD.filled(0)
            return np.array(pIBD, dtype=float).T

        @pymc.stochastic(observed=True)
        def marginal_bin(value=self.ibd, p=Phi, n=self.sz):
            return np.sum((value * np.log(p) + (n-value) *
                           np.log(1-p)).T * self.weight)


        Lsim = pymc.Container([[pymc.Binomial('Lsim_{}_{}'.format(i, j),
                                 n=self.sz[i][j],
                                 p=Phi[i][j])
                                 for j in xrange(self.ibd.shape[1])]
                                 for i in xrange(self.ibd.shape[0])])

        return locals()

    def run_model(self, it, burn, thin, outfile, plot, model_com=False):
        dbname = outfile + ".pickle"
        M = pymc.Model(self.make_model())
        S = pymc.MCMC(
            M, db='pickle', calc_deviance=True,
            dbname=dbname)
        S.sample(iter=it, burn=burn, thin=thin)
        S.db.close()
        # for i in xrange(self.nreps):
        # for j in xrange(self.ndc):
        # S.Lsim[i][j].summary()
        # if plot:
        # pymc.Matplot.gof_plot(
        # S.Lsim[i][j], self.data[i][j],
        # name="gof" + str(i) + str(j))
        S.sigma.summary()
        S.ss.summary()
        S.density.summary()
        S.nb.summary()
        S.neigh.summary()
        reps = np.array([['Lsim_{}_{}'.format(i, j) for j in xrange(
            self.ibd.shape[1])] for i in xrange(self.ibd.shape[0])])
        S.write_csv(
            outfile + ".csv", variables=["sigma", "ss", "density",
                                         "nb", "neigh"] + list(reps.flatten()))
        S.stats()
        if plot:
            pymc.Matplot.plot(S.ss, format="pdf")
            pymc.Matplot.plot(S.neigh, format="pdf")
            pymc.Matplot.plot(S.density, format="pdf")
            pymc.Matplot.plot(S.sigma, format="pdf")
            pymc.Matplot.plot(S.nb, format="pdf")
            # [S.ss, S.neigh, S.density, S.sigma, S.nb,
            # S.lognb, S.logss, S.logs])
        # trace = S.trace("neigh")[:]
        if model_com:
            NM = pymc.Model(self.make_null_model())
            NS = pymc.MCMC(NM, db='pickle', calc_deviance=True,
                           dbname=outfile + "_null.pickle")
            NS.sample(iter=it, burn=burn, thin=thin)
            reps = np.array([['Lsim_{}_{}'.format(i, j) for j in xrange(
                self.ibd.shape[1])] for i in xrange(self.ibd.shape[0])])
            NS.write_csv(outfile + "_null.csv",
                         variables=["sigma", "ss", "density", "nb", "neigh"] +
                         list(reps.flatten()))
            # pymc.raftery_lewis(trace, q=0.025, r=0.01)
            hoDIC = NS.dic
            haDIC = S.dic
            com_out = open(outfile + "_model_comp.txt", 'w')
            com_out.write("Null Hypothesis DIC: " + str(hoDIC) + "\n")
            com_out.write("Alt Hypothesis DIC: " + str(haDIC) + "\n")
            NS.db.close()
        # pymc.gelman_rubin(S)
        S.db.close()