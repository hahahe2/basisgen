from invariants.algebras import Series, SimpleAlgebra, SemisimpleAlgebra
from invariants.representations import Irrep
from invariants.weights import Weight


algebra = SemisimpleAlgebra([
    SimpleAlgebra(Series.A, 1),
    SimpleAlgebra(Series.A, 1)
])


def lorentz_irrep(n, m):
    return Irrep(algebra, Weight([round(2*n), round(2*m)]))


scalar = lorentz_irrep(0, 0)
L_spinor = lorentz_irrep(1/2, 0)
R_spinor = lorentz_irrep(0, 1/2)
vector = lorentz_irrep(1/2, 1/2)
L_tensor = lorentz_irrep(1, 0)
R_tensor = lorentz_irrep(0, 1)
