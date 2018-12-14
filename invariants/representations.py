from invariants.algebras import SemisimpleAlgebra
from invariants.weights import Weight
from invariants.statistics import Statistics
from invariants.containers import MultivaluedMap, OrderedCounter

import collections
import itertools
import functools


class Representation(object):
    def __init__(self, weights):
        self.weights = weights

    def __str__(self):
        return str(self.weights)

    __repr__ = __str__

    def __iter__(self):
        return iter(self.weights)

    def __mul__(self, other):
        return Representation(collections.Counter(
            first_weight + second_weight
            for first_weight in self.weights.elements()
            for second_weight in other.weights.elements()
        ))

    @functools.lru_cache(maxsize=None)
    def highest_weight(self, algebra):
        return max(self.weights, key=algebra.height)

    @functools.lru_cache(maxsize=None)
    def decompose(self, algebra):
        def _item_height(item):
            return algebra.height(item[0])

        remaining_weights = OrderedCounter(collections.OrderedDict(
            sorted(
                self.weights.items(),
                key=_item_height
            )
        ))

        irreps = collections.Counter()

        while remaining_weights:
            highest_weight, multiplicity = remaining_weights.popitem()
            current_irrep = Irrep(algebra, highest_weight)
            irreps[current_irrep] += multiplicity

            remaining_weights[highest_weight] = multiplicity
            remaining_weights -= collections.Counter({
                weight: count * multiplicity
                for weight, count in
                current_irrep.representation.weights.items()
            })

        return irreps


class Irrep(object):
    def __init__(self, algebra, highest_weight):
        self.algebra = algebra
        self.highest_weight = highest_weight

    def __str__(self):
        return "Irrep({algebra}, {highest_weight})".format(
            algebra=self.algebra,
            highest_weight=self.highest_weight
        )

    __repr__ = __str__

    def __add__(self, other):
        concatenated_weight = Weight(list(
            itertools.chain(self.highest_weight, other.highest_weight)
        ))
        return Irrep(self.algebra + other.algebra, concatenated_weight)

    def __hash__(self):
        return hash((self.algebra, tuple(self.highest_weight)))

    def __eq__(self, other):
        return (
            tuple(self.highest_weight) == tuple(other.highest_weight)
            and self.algebra == other.algebra
        )

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def positive_roots(algebra):
        roots = Irrep(algebra, algebra.highest_root).weights_by_level
        return list(
            itertools.chain.from_iterable(
                roots[level]
                for level in range(algebra.level_of_simple_roots + 1)
            )
        )

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def _mul_semisimple_irreps(first, second):
        first_irreps = map(
            Irrep,
            first.algebra.simple_algebras,
            first.algebra.split_weight(first.highest_weight)
        )

        second_irreps = map(
            Irrep,
            second.algebra.simple_algebras,
            second.algebra.split_weight(second.highest_weight)
        )

        out = collections.Counter()

        for combination in itertools.product(*(
                (first_irrep * second_irrep).items()
                for first_irrep, second_irrep
                in zip(first_irreps, second_irreps)
        )):
            irrep = combination[0][0]
            count = combination[0][1]
            for inner_irrep, inner_count in combination[1:]:
                irrep += inner_irrep
                inner_count *= inner_count

            out += collections.Counter({irrep: count})

        return out

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def _mul_simple_irreps(first, second):
        product_representation = (
            first.representation * second.representation
        )

        return product_representation.decompose(first.algebra)

    def __mul__(self, other):
        if isinstance(other, Irrep):
            are_semisimple = (
                isinstance(self.algebra, SemisimpleAlgebra)
                and isinstance(other.algebra, SemisimpleAlgebra)
            )

            if are_semisimple:
                return Irrep._mul_semisimple_irreps(self, other)
            else:
                return Irrep._mul_simple_irreps(self, other)

        else:
            return Irrep.product(collections.Counter([self]), other)

    __rmul__ = __mul__

    def __getitem__(self, index):
        return Irrep(self.algebra[index], self.highest_weight[index])

    @property
    def is_singlet(self):
        return all(component == 0 for component in self.highest_weight)

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def singlet(algebra):
        return Irrep(algebra, Weight([0] * algebra.rank))

    @staticmethod
    def product(first_irrep_counter, second_irrep_counter):
        return sum(
            (
                collections.Counter({
                    irrep: count * first_count * second_count
                    for irrep, count in (first_irrep * second_irrep).items()
                })
                for first_irrep, first_count in first_irrep_counter.items()
                for second_irrep, second_count in second_irrep_counter.items()
            ),
            collections.Counter()
        )

    def _child_weights(self, weight, level):
        return MultivaluedMap.from_pairs(
            (level + k, weight - k*root)
            for root, component in zip(self.algebra.simple_roots, weight)
            for k in range(1, component + 1)
        )

    @property
    def weights_by_level(self):
        current_weights = self._child_weights(self.highest_weight, 0)
        all_weights = MultivaluedMap({0: {self.highest_weight}})

        while current_weights:
            previous_weights = current_weights
            current_weights = MultivaluedMap()

            for level in previous_weights:
                for weight in previous_weights[level]:
                    current_weights.update(self._child_weights(weight, level))

            all_weights.update(previous_weights)

        return all_weights

    def _weight_multiplicity(self, level, weight, previous_multiplicities):
        if level == 0:
            return 1

        delta = self.algebra.sum_of_positive_roots

        numerator = 2 * sum(
            previous_multiplicities.get(weight + k*alpha, 0)
            * self.algebra.scalar_product(weight + k*alpha, alpha)
            for k in range(1, level + 1)
            for alpha in Irrep.positive_roots(self.algebra)
        )

        denominator = (
            self.algebra.norm_squared(self.highest_weight + delta)
            - self.algebra.norm_squared(weight + delta)
        )

        return round(numerator / denominator)

    @property
    def weights_with_multiplicities(self):
        multiplicities = collections.Counter()

        for level, weights in self.weights_by_level.items():
            for weight in weights:
                multiplicities[weight] = self._weight_multiplicity(
                    level,
                    weight,
                    multiplicities
                )

        return multiplicities

    @property
    def _semisimple_representation(self):
        algebras = self.algebra.simple_algebras
        split_highest_weight = self.algebra.split_weight(self.highest_weight)

        split_weights = (
            Irrep(algebra, weight).representation.weights.elements()
            for algebra, weight in zip(algebras, split_highest_weight)
        )

        return Representation(collections.Counter([
            Weight(list(itertools.chain.from_iterable(weights)))
            for weights in itertools.product(*split_weights)
        ]))

    @property
    def representation(self):
        if isinstance(self.algebra, SemisimpleAlgebra):
            return self._semisimple_representation
        else:
            return Representation(self.weights_with_multiplicities)

    @functools.lru_cache(maxsize=None)
    def power(self, exponent, statistics):
        combinations_function = {
            Statistics.BOSON: itertools.combinations_with_replacement,
            Statistics.FERMION: itertools.combinations
        }[statistics]

        weights = self.representation.weights.elements()

        power_weights = collections.Counter([
            sum(combination, Irrep.singlet(self.algebra).highest_weight)
            for combination in combinations_function(weights, exponent)
        ])

        return Representation(power_weights).decompose(self.algebra)
