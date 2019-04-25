"""
model.py

Pyro models from bayesian inference on data
"""
import pyro
import pyro.distributions as dist

import torch

from holopy.scattering import Sphere, calc_holo

class BaseModel(object):
    """Base Model for bayesian inference
    """
    def __init__(self, params):
        self.params = params
        self.param_names = list(self.params.keys())

    def __call__(self, data):
        return self.model(data)

    def model(self, data):
        x = data['x']
        y = data['y']
        return pyro.condition(self.likelihood, data={'likelihood': y})(x)

    def likelihood(self, x):
        raise NotImplementedError("Implement in subclass")

    def forward(self, x, params):
        raise NotImplementedError("Implement in subclass")


class NormalModel(BaseModel):
    """Model where all parameters have Gaussian priors. The initial params dict 
    specifies gaussian priors as {(loc, scale) for loc, scale in params.items()}
    """
    def likelihood(self, x):
        """
        """
        params = {k: pyro.sample(k, dist.Normal(*v)) 
                  for k, v in self.params.items()}
        noise_sd = 0.1
        expected = self.forward(x, params)
        return pyro.sample('likelihood', dist.Normal(expected, noise_sd**2))


class NoisyNormalModel(BaseModel):
    """Model where all parameters have Gaussian priors, except the noise_sd, 
    which log-normal distributed. This allows us to estimate noise in the data
    The initial params dict specifies the priors as 
    {(loc, scale) for loc, scale in params.items()}
    """
    def likelihood(self, x):
        """Since noise is included as parameter, sample ln_noise from Normal
        """
        params = {}
        for k, v in self.params.items():
            if k == 'noise_sd':
                ln_sigma = torch.log(torch.tensor(v[0]))
                ln_sigma_var = torch.log(torch.tensor(v[1]))
                param = pyro.sample(k, dist.Normal(ln_sigma, ln_sigma_var))
            else:
                param = pyro.sample(k, dist.Normal(*v))
            params[k] = param
        
        expected = self.forward(x, params)
        noise = torch.exp(params['noise_sd']) ** 2

        return pyro.sample('likelihood', dist.Normal(expected, noise))


class HolopyAlphaModel(NoisyNormalModel):
    def forward(self, x, params):
        x0 = params['x'].detach().numpy()
        x1 = params['y'].detach().numpy()
        x2 = params['z'].detach().numpy()
        n = params['n'].detach().numpy()
        r = params['r'].detach().numpy()
        alpha = params['alpha'].detach().numpy()

        sph = Sphere(center = (x0, x1, x2), n=n, r=r)
        mod = calc_holo(x, sph, scaling=alpha).values.squeeze()
        return torch.from_numpy(mod)

    def convert_holopy(self, data):
        x = data
        y = torch.from_numpy(data.values.squeeze())
        return {'x': x, 'y': y}