import numpy as np
from scipy import optimize
from . import (losses, transformers)

# helper function for our softmax "trick" with l[0]=0
def _np_softmax(l):
  exp_l = np.exp(np.concatenate(([0.], l)))
  return exp_l / exp_l.sum()

# helper function for proper labels from 0 to n_classes-1
def _sanitize_labels(y):
  if y.min() == 1:
    y -= 1
  elif y.min() != 0:
    raise ValueError("y.min() ∉ [0, 1]")
  labels = np.sort(np.unique(y))
  if np.any(labels != np.arange(y.max()+1)):
    raise ValueError("Not all labels between y.min() and y.max() are present:")
  return y, len(labels) # = (y, C)

class Result(np.ndarray): # https://stackoverflow.com/a/67510022/20580159
  """A numpy array with additional properties nit and message."""
  def __new__(cls, input_array, nit, message):        
    obj = np.asarray(input_array).view(cls)
    obj.nit = nit
    obj.message = message
    return obj
  def __array_finalize__(self, obj):
    if obj is None:
      return
    self.nit = getattr(obj, "nit", None)
    self.message = getattr(obj, "message", None)

class GenericMethod:
  """A generic quantification / unfolding method."""
  def __init__(self, loss, transformer, solver="trust-exact", seed=None, verbose=False):
    self.loss = loss
    self.transformer = transformer
    self.solver = solver
    self.seed = seed
    self.verbose = verbose
  def fit(self, X, y):
    y, C = _sanitize_labels(y)
    fX, fy = self.transformer.fit_transform(X, y) # f(x) for x ∈ X
    M = np.zeros((fX.shape[1], C)) # (n_features, n_classes)
    for c in range(C):
      M[:,c] = fX[fy==c,:].sum(axis=0) # one histogram of f(X) per class
    self.M = M / M.sum(axis=0, keepdims=True)
    self.p_trn = M.sum(axis=0) / M.sum()
    return self
  def predict(self, X):
    q = self.transformer.transform(X).mean(axis=0)
    return self.solve(q, self.M)
  def solve(self, q, M): # TODO add arguments p_trn and N=X.shape[0]
    loss_dict = losses.instantiate_loss(self.loss, q, M, self.verbose)
    rng = np.random.RandomState(self.seed)
    if self.verbose:
      print("DEBUG: Optimizing")
    opt = optimize.minimize(
      loss_dict["fun"],
      rng.rand(loss_dict["n_classes"]-1), # l_0
      jac = loss_dict["jac"],
      hess = loss_dict["hess"],
      method = self.solver,
    )
    return Result(_np_softmax(opt.x), opt.nit, opt.message)

class ACC(GenericMethod):
  """Adjusted Classify & Count."""
  def __init__(self, classifier, fit_classifier=True, **kwargs):
    GenericMethod.__init__(
      self,
      losses.LeastSquaresLoss(),
      transformers.ClassTransformer(
        classifier,
        fit_classifier = fit_classifier
      ),
      **kwargs
    )

class PACC(GenericMethod):
  """Probabilistic Adjusted Classify & Count."""
  def __init__(self, classifier, fit_classifier=True, **kwargs):
    GenericMethod.__init__(
      self,
      losses.LeastSquaresLoss(),
      transformers.ClassTransformer(
        classifier,
        fit_classifier = fit_classifier,
        is_probabilistic = True
      ),
      **kwargs
    )
