
import numpy as np
import cvxopt.solvers
import logging


# Lagrange multipliers tolerance
MIN_SUPPORT_VECTOR_MULTIPLIER = 1e-5


class SVMPredictor(object):
    
    def __init__(self,
                 kernel,
                 bias,
                 weights,
                 support_vectors,
                 support_vector_labels):

        self._kernel = kernel
        self._bias = bias
        self._weights = weights
        self._support_vectors = support_vectors
        self._support_vector_labels = support_vector_labels
        
        assert len(support_vectors) == len(support_vector_labels)
        assert len(weights) == len(support_vector_labels)

        logging.info("Bias: %s", self._bias)
        logging.info("Weights: %s", self._weights)
        logging.info("Support vectors: %s", self._support_vectors)
        logging.info("Support vector labels: %s", self._support_vector_labels)

    def predict(self, x):
        """
        Computes the SVM prediction on the given features x.
        """
        result = self._bias
        # TODO(josman) : vectorize
        for z_i, x_i, y_i in zip(self._weights,
                                 self._support_vectors,
                                 self._support_vector_labels):
            result += z_i * y_i * self._kernel(x_i, x)
        return np.sign(result).item()


class SVMTrainer(object):

    def __init__(self, kernel, c):
        """Set initial parameters."""
        self._kernel = kernel
        self._c = c

    def _kernel_matrix(self, X):
        """Build the kernel matrix."""
        n_samples, n_features = X.shape
        K = np.zeros((n_samples, n_samples))
        # TODO(josman) : vectorize
        for i, x_i in enumerate(X):
            for j, x_j in enumerate(X):
                K[i, j] = self._kernel(x_i, x_j)
        return K

    def _optimization_dual(self, X, y):
        """Solve the dual SVM optimization problem."""

        n_samples, n_features = X.shape

        K = self._kernel_matrix(X)
        # Solves
        # min     1/2 x^T P x - e^t x
        # s.a.    y^t x = 0
        #         0 <= x <= c

        # Objective function
        P = cvxopt.matrix(np.outer(y, y) * K)
        e = cvxopt.matrix(-1 * np.ones(n_samples))

        # y^t x = 0
        A = cvxopt.matrix(y, (1, n_samples))
        b = cvxopt.matrix(0.0)

        # -x <= 0
        G_l = cvxopt.matrix(np.diag(np.ones(n_samples)) * -1)
        h_l = cvxopt.matrix(np.zeros(n_samples))

        # x <= c
        G_u = cvxopt.matrix(np.diag(np.ones(n_samples)))
        h_u = cvxopt.matrix(np.ones(n_samples) * self._c)

        G = cvxopt.matrix(np.vstack((G_l, G_u)))
        h = cvxopt.matrix(np.vstack((h_l, h_u)))

        solution = cvxopt.solvers.qp(P, e, G, h, A, b)

        # Return Lagrange multipliers
        return np.ravel(solution['x'])

    def _optimization_dual_linear(self, X, y, mu):
        """
        Solves the dual problem with linear kernel.
        Modifies the problem so we don't need to
        compute XX^T. We use logarithmic barrier.
        """

        n_samples, n_features = X.shape

        # Solves
        # min     1/2 z^t z - e^t x
        # s.a.    b^t x = 0
        #         Ax - z = 0
        #         x - c e >= 0
        #         x >= 0
        #
        # Where A = X^t Y

        # Objective function
        P = cvxopt.matrix(np.vstack(
            (
                np.eye(n_features),
                np.zeros((n_samples, n_features)),
            )
        ))

        # Hasta aquí llego
        e = cvxopt.matrix(
            np.vstack(
                (
                    np.zeros((n_features, 1)),
                    -1 * np.ones((n_samples, 1)),
                )
            )
        )

        # y^t x = 0
        A = cvxopt.matrix(
            np.hstack((np.zeros((1, n_features)), y.reshape(1, n_samples)))
        )
        b = cvxopt.matrix(0.0)

        # -x <= 0
        G_l = cvxopt.matrix(np.diag(np.ones(n_samples)) * -1)
        h_l = cvxopt.matrix(np.zeros(n_samples))

        # x <= c
        G_u = cvxopt.matrix(np.diag(np.ones(n_samples)))
        h_u = cvxopt.matrix(np.ones(n_samples) * self._c)

        G = cvxopt.matrix(np.vstack((G_l, G_u)))
        h = cvxopt.matrix(np.vstack((h_l, h_u)))

        solution = cvxopt.solvers.qp(P, e, G, h, A, b)

        # Return Lagrange multipliers
        return np.ravel(solution['x'])

    def _construct_predictor(self, X, y, lagrange_multipliers):
        """Compute bias and construct predictor."""
        support_vector_indices = \
            lagrange_multipliers > MIN_SUPPORT_VECTOR_MULTIPLIER

        support_multipliers = lagrange_multipliers[support_vector_indices]
        support_vectors = X[support_vector_indices]
        support_vector_labels = y[support_vector_indices]

        # bias = y_k - \sum z_i y_i K(x_k, x_i)
        # Thus we can just predict an example with bias of zero, and
        # compute error.
        bias = np.mean(
            [y_k - SVMPredictor(
                    kernel=self._kernel,
                    bias=0.0,
                    weights=support_multipliers,
                    support_vectors=support_vectors,
                    support_vector_labels=support_vector_labels).predict(x_k)
             for (y_k, x_k) in zip(support_vector_labels, support_vectors)])

        return SVMPredictor(
            kernel=self._kernel,
            bias=bias,
            weights=support_multipliers,
            support_vectors=support_vectors,
            support_vector_labels=support_vector_labels)

    def train(self, X, y):
        """Given the training features X with labels y, returns a SVM
        predictor representing the trained SVM.
        """
        lagrange_multipliers = self._optimization_dual(X, y)
        return self._construct_predictor(X, y, lagrange_multipliers)
