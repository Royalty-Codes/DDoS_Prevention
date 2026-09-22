import unittest

from sdn_ddos.contracts import DATASET_COLUMNS, LABELS, SCENARIOS, scenario_for


class ContractTests(unittest.TestCase):
    def test_28_column_contract_is_stable(self) -> None:
        self.assertEqual(len(DATASET_COLUMNS), 28)
        self.assertEqual(DATASET_COLUMNS[-3:], ("label", "attack_family", "data_source"))

    def test_11_labels_have_one_scenario_each(self) -> None:
        self.assertEqual(len(LABELS), 11)
        self.assertEqual(len(set(LABELS)), 11)
        self.assertEqual(tuple(scenario.label for scenario in SCENARIOS), LABELS)
        self.assertEqual(scenario_for("BENIGN").family, "BENIGN")
