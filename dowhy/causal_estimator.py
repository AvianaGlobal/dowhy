import logging

import numpy as np
import sympy as sp


class CausalEstimator:
    """Base class for an estimator of causal effect.

    """

    def __init__(self, data, identified_estimand, treatment, outcome,
                 test_significance, evaluate_effect_strength=True,
                 target_units=None, heterogeneous_effect_vars=None,
                 params=None):
        """Initializes an estimator with data and names of relevant variables.

        More description.

        :param data: data frame containing the data
        :param identified_estimand: probability expression
            representing the target identified estimand to estimate.
        :param treatment: name of the treatment variable
        :param outcome: name of the outcome variable
        :param test_significance: whether to test significance
        :param evaluate_effect_strength: whether to evaluate the strength of effect
        :param target_units: ATE, ATT or another subset of units (not implemented)
        :param heterogeneous_effect_vars: variables on which to compute separate effects, or return a heterogeneous effect function (not implemented)
        :param params: (optional) additional method parameters
        :returns: an instance of the estimator class.

        """
        self._data = data
        self._target_estimand = identified_estimand
        # Currently estimation methods only support univariate treatment and outcome
        self._treatment_name = treatment[0]
        self._outcome_name = outcome[0]
        self._significance_test = test_significance
        self._effect_strength_eval = evaluate_effect_strength
        self._target_units = target_units
        self.heterogeneous_effect_vars = heterogeneous_effect_vars
        self._estimate = None
        if params is not None:
            for key, value in params.items():
                setattr(self, key, value)

        self.logger = logging.getLogger(__name__)

    def _estimate_effect(self):
        raise NotImplementedError

    def estimate_effect(self):
        """TODO.

        More description.

        :param self: object instance of class Estimator
        :returns: point estimate of causal effect

        """
        self._treatment = self._data[self._treatment_name]
        self._outcome = self._data[self._outcome_name]
        est = self._estimate_effect()
        self._estimate = est


        if self._significance_test:
            signif_dict = self.test_significance(est)
            est.add_significance_test_results(signif_dict)
        if self._effect_strength_eval:
            effect_strength_dict = self.evaluate_effect_strength(est)
            est.add_effect_strength(effect_strength_dict)

        return est

    def estimate_effect_naive(self):
        df_treatment = self._data.loc[self._data[self._treatment_name] == 1]
        df_notreatment = self._data.loc[self._data[self._treatment_name]== 0]
        est = np.mean(df_treatment[self._outcome_name]) - np.mean(df_notreatment[self._outcome_name])
        return CausalEstimate(est, None, None)

    def _do(self, x):
        raise NotImplementedError

    def do(self, x):
        """TODO.

        More description.

        :param arg1:
        :returns:

        """
        self._treatment = self._data[self._treatment_name]
        self._outcome = self._data[self._outcome_name]
        est = self._do(x)

        return est

    def construct_symbolic_estimator(self, estimand):
        raise NotImplementedError

    def test_significance(self, estimate, num_simulations=1000):
        """Test statistical significance of obtained estimate.

        Uses resampling to create a non-parametric significance test.
        A general procedure. Individual estimators can override this method.

        :param self: object instance of class Estimator
        :param estimate: obtained estimate
        :returns:

        """
        if not hasattr(self,'num_simulations'):
            self.num_simulations = num_simulations
        null_estimates = np.zeros(self.num_simulations)
        for i in range(self.num_simulations):
            self._outcome = np.random.permutation(self._outcome)
            est = self._estimate_effect()
            null_estimates[i] = est.value

        sorted_null_estimates = np.sort(null_estimates)
        self.logger.debug("Null estimates: {0}".format(sorted_null_estimates))
        median_estimate = sorted_null_estimates[int(self.num_simulations / 2)]
        # Doing a two-sided test
        if estimate.value > median_estimate:
            # Being conservative with the p-value reported
            estimate_index = np.searchsorted(sorted_null_estimates, estimate.value, side="left")
            p_value = 1 - (estimate_index / self.num_simulations)
        if estimate.value <= median_estimate:
            # Being conservative with the p-value reported
            estimate_index = np.searchsorted(sorted_null_estimates, estimate.value, side="right")
            p_value = (estimate_index / self.num_simulations)
        signif_dict = {
            'p_value': p_value,
            'sorted_null_estimates': sorted_null_estimates
        }
        return signif_dict

    def evaluate_effect_strength(self, estimate):
        fraction_effect_explained = self._evaluate_effect_strength(estimate, method="fraction-effect")
        # Need to test r-squared before supporting
        #effect_r_squared = self._evaluate_effect_strength(estimate, method="r-squared")
        strength_dict = {
                'fraction-effect': fraction_effect_explained
         #       'r-squared': effect_r_squared
                }
        return strength_dict

    def _evaluate_effect_strength(self, estimate, method="fraction-effect"):
        supported_methods = ["fraction-effect"]
        if method not in supported_methods:
            raise NotImplementedError("This method is not supported for evaluating effect strength")
        if method == "fraction-effect":
            naive_obs_estimate = self.estimate_effect_naive()
            fraction_effect_explained = estimate.value/naive_obs_estimate.value
            return fraction_effect_explained
        #elif method == "r-squared":
        #    outcome_mean = np.mean(self._outcome)
        #    total_variance = np.sum(np.square(self._outcome - outcome_mean))
            # Assuming a linear model with one variable: the treatment
            # Currently only works for continuous y
        #    causal_model = outcome_mean + estimate.value*self._treatment
        #    squared_residual = np.sum(np.square(self._outcome - causal_model))
        #    r_squared = 1 - (squared_residual/total_variance)
        #    return r_squared
        else:
            return None

class CausalEstimate:
    """TODO.

    """

    def __init__(self, estimate, target_estimand, realized_estimand_expr, **kwargs):
        self.value = estimate
        self.target_estimand = target_estimand
        self.realized_estimand_expr = realized_estimand_expr
        self.params = kwargs
        self.significance_test = None
        self.effect_strength = None

    def add_significance_test_results(self, test_results):
        self.significance_test = test_results

    def add_effect_strength(self, strength_dict):
        self.effect_strength = strength_dict

    def add_params(self, **kwargs):
        self.params.update(kwargs)

    def __str__(self):
        s = "*** Causal Estimate ***\n"
        s += "\n## Target estimand\n{0}".format(self.target_estimand)
        s += "\n## Realized estimand\n{0}".format(self.realized_estimand_expr)
        s += "\n## Estimate\n"
        s += "Value: {0}\n".format(self.value)
        if self.significance_test is not None:
            s += "\n## Statistical Significance\n"
            if self.significance_test["p_value"]>0:
                s += "p-value: {0}\n".format(self.significance_test["p_value"])
            else:
                s+= "p-value: <{0}\n".format(1/len(self.significance_test["sorted_null_estimates"]))
        if self.effect_strength is not None:
            s += "\n## Effect Strength\n"
            s += "Change in outcome attributable to treatment: {}\n".format(self.effect_strength["fraction-effect"])
            #s += "Variance in outcome explained by treatment: {}\n".format(self.effect_strength["r-squared"])
        return s


class RealizedEstimand(object):

    def __init__(self, identified_estimand, estimator_name):
        self.treatment_variable = identified_estimand.treatment_variable
        self.outcome_variable = identified_estimand.outcome_variable
        self.backdoor_variables = identified_estimand.backdoor_variables
        self.instrumental_variables = identified_estimand.instrumental_variables
        self.estimand_type = identified_estimand.estimand_type
        self.estimand_expression = None
        self.assumptions = None
        self.estimator_name = estimator_name

    def update_assumptions(self, estimator_assumptions):
        self.assumptions = estimator_assumptions

    def update_estimand_expression(self, estimand_expression):
        self.estimand_expression = estimand_expression

    def __str__(self):
        s = "Realized estimand: {0}\n".format(self.estimator_name)
        s += "Realized estimand type: {0}\n".format(self.estimand_type)
        s += "Estimand expression:\n{0}\n".format(sp.pretty(self.estimand_expression))
        j = 1
        for ass_name, ass_str in self.assumptions.items():
            s += "Estimand assumption {0}, {1}: {2}\n".format(j, ass_name, ass_str)
            j += 1
        return s

