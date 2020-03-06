import ast
from collections import defaultdict
from dataclasses import dataclass
import networkx as nx
from functools import reduce


@dataclass
class Call:
    obj: object
    is_conditional: bool
    is_loop: bool


class FunctionCounter(ast.NodeVisitor):
    def __init__(self, filename=None):
        self.filename = filename

        self.index = {}
        self.graph = defaultdict(list)
        self.imports = defaultdict(list)
        self.aliases = {}

    def read_file(self):
        with open(self.filename, 'r') as f:
            self.ast = ast.parse(f.read())
        self.visit(self.ast)

    def __repr__(self):
        return f"FunctionCounter({self.filename})"

    def __str__(self):
        return self.filename

    def visit_Import(self, node):
        for i in node.names:
            if i.asname:
                self.aliases[i.name] = i.asname
            self.imports[i.name]
        super().generic_visit(node)

    def visit_ImportFrom(self, node):
        for i in node.names:
            if i.asname:
                self.aliases[i.name] = i.asname
            self.imports[node.module].append(i.name)
        super().generic_visit(node)

    def visit_FunctionDef(self, node):
        self.index[node.name] = node
        self._register_calls(node, node)

    def visit_ClassDef(self, node):
        self.index[node.name] = node
        self._register_calls(node, node)

    def visit_For(self, node):
        self._register_calls(node, node, is_loop=True)

    def visit_While(self, node):
        self._register_calls(node, node, is_loop=True)

    def visit_GeneratorExp(self, node):
        self._register_calls(node, node, is_loop=True)

    def visit_ListComp(self, node):
        self._register_calls(node, node, is_loop=True)

    def visit_DictComp(self, node):
        self._register_calls(node, node, is_loop=True)

    def visit_SetComp(self, node):
        self._register_calls(node, node, is_loop=True)

    def visit_comprehension(self, node):
        self._register_calls(node, node, is_loop=True)

    def _register_calls(self, node, parent_node,
                        is_conditional=False,
                        is_loop = False):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                self.graph[parent_node].append(Call(func, is_conditional, is_loop))
            elif isinstance(func, ast.Attribute):
                # We have a method call
                pass
        else:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef):
                    # If we have a nested function
                    self.index[child.name] = child

                if isinstance(child, (ast.If, ast.IfExp)):
                    self._register_calls(child, parent_node, is_conditional=True, is_loop=is_loop)
                elif isinstance(child, (ast.For, ast.While)):
                    self._register_calls(child, parent_node, is_loop=True, is_conditional=is_conditional)
                else:
                    self._register_calls(child, parent_node, is_conditional=is_conditional, is_loop=is_loop)

    @property
    def pretty_calls(self):
        rv = {}
        for f, v in self.graph.items():
            rv[f.name] = list()
            for v1 in v:
                rv[f.name].append(v1.obj.id)
        return rv


def to_networkx(fnc, filter_builtins=True):
    """Turn a FunctionCounter into an annotated networkx graph.

    Args:
        fnc: FunctionCounter instance
        filter_builtins: Filter out builtin function calls

    Returns:
        (networkx.MultiDiGraph)
            edges represent calls to functions and are annotated if they
            occur within a conditional block or looping construct.
    """
    G = nx.MultiDiGraph()
    _builtins = set(dir(__builtins__))
    for v1, v2 in fnc.graph.items():
        for e in v2:
            if (filter_builtins and e.obj.id not in _builtins) or not filter_builtins:
                G.add_edge(v1.name, e.obj.id, in_conditional=e.is_conditional, in_loop=e.is_loop)
    return G

# Colormaps are defined by:
# {(in_conditional?, in_loop?): color code}
colors = {(True, True): 'brown', (True, False): 'cyan', (False, True): 'red', (False, False): 'black'}

def color_vector(G, colormap):
    cl = []
    for u, v, data in G.edges(data=True):
        key = data['in_conditional'], data['in_loop']
        cl.append(colormap[key])
    return cl

def merge_networkx(fncs, filter_builtins=True):
    """ Merge multiple function counter instances into a single graph """
    gfs = (to_networkx(f, filter_builtins=filter_builtins) for f in fncs)
    return reduce(nx.compose, gfs)
