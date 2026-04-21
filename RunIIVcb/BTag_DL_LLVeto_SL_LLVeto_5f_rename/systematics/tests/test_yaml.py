import yaml
import unittest


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = set()
        for key_node, value_node in node.value:
            if ':merge' in key_node.tag:
                continue 
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate {key!r} key found in YAML.")
            mapping.add(key)
        return super().construct_mapping(node, deep)

# other code
class TestYaml(unittest.TestCase):

    def setUp(self):
        self.yaml_path = "systematics_master.yml"

    def test_unique_keys(self):
        with open(self.yaml_path) as yaml_file:
            yaml_dic=yaml.load(yaml_file,Loader=UniqueKeyLoader)
