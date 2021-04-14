"""
Generates fairgraph classes.

The contents of target/fairgraph should be copied into the fairgraph/openminds directory
"""

import os
import re
from typing import List
from collections import defaultdict


from generator.commons import (JinjaGenerator, TEMPLATE_PROPERTY_TYPE,
    TEMPLATE_PROPERTY_LINKED_TYPES, SchemaStructure, TEMPLATE_PROPERTY_EMBEDDED_TYPES,
    TARGET_PATH, SCHEMA_FILE_ENDING)


name_map = {
    "shortName": "alias",
    "fullName": "name",
    "scope": "model_scope",
    "hasVersion": "versions"
}

def generate_python_name(json_name, allow_multiple=False):
    if json_name in name_map:
        python_name = name_map[json_name]
    else:
        python_name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", json_name)
        python_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", python_name).lower()
        if allow_multiple:
            # todo: make this more sophisticated, e.g. avoid "data" --> "datas", "fundings", etc.
            python_name += "s"
    return python_name


type_name_map = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "date-time": "datetime"
}

format_map = {
    "iri": "IRI",
    "date": "date"
}


def generate_class_name(iri):
    parts = iri.split("/")[-2:]
    for i in range(len(parts) - 1):
        parts[i] = parts[i].lower()
    return "openminds." + ".".join(parts)


def generate_doc(property, obj_title):
    doc = property.get("description", "no description available")
    doc = doc.replace("someone or something", f"the {obj_title.lower()}")
    doc = doc.replace("something or somebody", f"the {obj_title.lower()}")
    return doc


class FairgraphGenerator(JinjaGenerator):

    def __init__(self, schema_information:List[SchemaStructure]):
        super().__init__("py", None, "fairgraph_module_template.py.txt")
        self.target_path = os.path.join(TARGET_PATH, "fairgraph")
        self.schema_information = schema_information
        self.schema_information_by_type = {}
        #self.schema_collection_by_group = {}
        for s in self.schema_information:
            self.schema_information_by_type[s.type] = s
        self.import_data = defaultdict(dict)

    def _pre_process_template(self, schema):
        schema_information = self.schema_information_by_type[schema[TEMPLATE_PROPERTY_TYPE]]
        schema["simpleTypeName"] = os.path.basename(schema[TEMPLATE_PROPERTY_TYPE])
        schema["schemaGroup"] = schema_information.schema_group.split("/")[0]
        schema["schemaVersion"] = schema_information.version
        # if schema["schemaGroup"] not in self.schema_collection_by_group:
        #     self.schema_collection_by_group[schema["schemaGroup"]] = []
        # self.schema_collection_by_group[schema["schemaGroup"]].append(schema_information)

        fields = []
        #imports = set([])
        for name, property in schema["properties"].items():
            allow_multiple = False
            if property.get("type") == "array":
                allow_multiple = True
            if TEMPLATE_PROPERTY_LINKED_TYPES in property:
                possible_types = [
                    f'"{generate_class_name(iri)}"'
                    for iri in property[TEMPLATE_PROPERTY_LINKED_TYPES]
                ]
            elif TEMPLATE_PROPERTY_EMBEDDED_TYPES in property:
                possible_types = [
                    f'"{generate_class_name(iri)}"'
                    for iri in property[TEMPLATE_PROPERTY_EMBEDDED_TYPES]
                ]  # todo: handle minItems maxItems, e.g. for axesOrigin
            elif "_format" in property:
                assert property["type"] == "string"
                possible_types = [format_map[property["_format"]]]
            elif property.get("type") == "array":
                possible_types = [type_name_map[property["items"]["type"]]]
            else:
                possible_types = [type_name_map[property["type"]]]
            #imports.update(possible_types)
            if len(possible_types) == 1:
                possible_types_str = possible_types[0]
            else:
                possible_types_str = "[{}]".format(", ".join(possible_types))
            field = {
                "name": generate_python_name(name, allow_multiple),
                "type": possible_types_str,
                "iri": f"vocab:{name}",
                "allow_multiple": allow_multiple,
                "required": name in schema.get("required", []),
                "doc": generate_doc(property, schema["title"])
            }
            fields.append(field)

        # for builtin_type in ("str", "int", "float"):
        #     try:
        #         imports.remove(builtin_type)
        #     except KeyError:
        #         pass

        # if imports:
        #     if len(imports) == 1:
        #         import_str = f"from fairgraph.openminds.?? import {list(imports)[0]}"
        #     else:
        #         import_str = "from fairgraph.openminds.?? import ({})".format(", ".join(sorted(imports)))
        # else:
        #     import_str = ""
        context = {
            #"imports": import_str,
            "class_name": generate_class_name(schema[TEMPLATE_PROPERTY_TYPE]).split(".")[-1],
            "default_space": "model",
            "base_class": "KGObject",
            "openminds_type": schema[TEMPLATE_PROPERTY_TYPE],
            "docstring": schema.get("description", ""),
            "fields": fields,
            "existence_query_fields": None
        }
        schema.update(context)
        self.import_data[schema["schemaGroup"]][schema[TEMPLATE_PROPERTY_TYPE]] = {
            "class_name": context["class_name"]
        }
        return schema

    def _generate_target_file_path(self, schema_group, schema_group_path, schema_path):
        relative_schema_path = os.path.dirname(schema_path[len(schema_group_path) + 1:])
        relative_schema_path = relative_schema_path.replace("-", "_")
        schema_file_name = os.path.basename(schema_path)
        schema_file_name_without_extension = generate_python_name(schema_file_name[:-len(SCHEMA_FILE_ENDING)])
        schema_group = schema_group.split("/")[0].lower()
        target_path = os.path.join(self.target_path, schema_group, relative_schema_path,
                                   f"{schema_file_name_without_extension}.{self.format}")
        return target_path

    def _generate_additional_files(self, schema_group, schema_group_path, schema_path, schema):
        relative_schema_path = os.path.dirname(schema_path[len(schema_group_path) + 1:])
        relative_schema_path = relative_schema_path.replace("-", "_")
        schema_group = schema_group.split("/")[0]
        path_parts = (self.target_path, schema_group.lower(), *relative_schema_path.split("/"))
        # create directories
        os.makedirs(os.path.join(*path_parts), exist_ok=True)
        # write __init__.py files
        schema_file_name = os.path.basename(schema_path)
        path = relative_schema_path.replace("/", ".") + f".{generate_python_name(schema_file_name[:-len(SCHEMA_FILE_ENDING)])}"
        if path[0] != ".":
            path = "." + path
        self.import_data[schema_group][schema[TEMPLATE_PROPERTY_TYPE]]["path"] = path

        for i in range(len(path_parts) + 1):
            path = os.path.join(*path_parts[:i], "__init__.py")
            if not os.path.exists(path):
                with open(path, "w") as fp:
                    fp.write("")

    def generate(self, ignore=None):
        super().generate(ignore=ignore)
        for schema_group, group_contents in self.import_data.items():
            path = os.path.join(self.target_path, schema_group, "__init__.py")
            with open(path, "w") as fp:
                for module in group_contents.values():
                    fp.write(f"from {module['path']} import {module['class_name']}\n")
        path = os.path.join(self.target_path, "__init__.py")
        with open(path, "w") as fp:
            fp.write("from . import {}\n".format(", ".join([key.lower() for key in self.import_data])))


if __name__ == "__main__":
    FairgraphGenerator([]).generate()
