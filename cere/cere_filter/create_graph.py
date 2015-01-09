#!/usr/bin/env python

import os
import re
import subprocess
import cere_configure
import logging
import cPickle as pickle
import networkx as nx
import matplotlib.pyplot as plt
from graph_utils import plot, save_graph

def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath = program.split()
    for v in fpath:
        if is_exe(v):
            return v
    return None

def parse_line(regex_list, line):
    i=-1
    matchObj=""
    while not matchObj:
        try:
            i = i + 1
            matchObj = re.match( regex_list[i], line )
        except IndexError:
            break
    return matchObj, i

def add_node(digraph, matchObj):
    _id = matchObj.group(1)
    name = matchObj.group(2)
    tested = False

    try:
        coverage = float(matchObj.group(6))
    except IndexError:
        coverage = 0.0

    if "__extracted__"  in name: valid = True
    else:
        valid = False

    if coverage >= 1 or float(matchObj.group(4)) >=1:
        small = False
    else:
        small = True

    digraph.add_node(_id, _name = name)
    digraph.node[_id]['_self_coverage'] = float(matchObj.group(4))
    digraph.node[_id]['_coverage'] = coverage
    digraph.node[_id]['_matching'] = False
    digraph.node[_id]['_error'] = 100.0
    digraph.node[_id]['_valid'] = valid
    digraph.node[_id]['_tested'] = tested
    digraph.node[_id]['_small'] = small
    return digraph

def remove_cycles(digraph, cycle):
    if len(cycle) == 1:
        digraph.remove_edge(cycle[0],cycle[0])
    else:
        parents = []
        childs = []
        toKeep = cycle[0]
        for node in cycle:
            #find parents
            for predecessor in digraph.predecessors(node):
                if predecessor not in cycle:
                    parents.append({'id' : predecessor, 'weight' : digraph.edge[predecessor][node]['weight']})
            #find childs
            for successor in digraph.successors(node):
                if successor not in cycle:
                    childs.append({'id' : successor, 'weight' : digraph.edge[node][successor]['weight']})
            #keep the node with the highest coverage
            if digraph.node[node]['_coverage'] > digraph.node[toKeep]['_coverage']:
                toKeep = node
        #Backup the node to keep
        replacer = digraph.node[toKeep]
        #remove the cycle
        digraph.remove_nodes_from(cycle)
        #replace it by the node to keep
        digraph.add_node(toKeep, replacer)
        #restore edges
        for parent in parents:
            if digraph.has_edge(parent['id'], toKeep):
                w = int(digraph.edge[parent['id']][toKeep]['weight'] + parent['weight'])
            else:
                w = int(parent['weight'])
            digraph.add_edge(parent['id'], toKeep, weight=w)
        for child in childs:
            if digraph.has_edge(toKeep, child['id']):
                w = int(digraph.edge[toKeep][child['id']]['weight'] + child['weight'])
            else:
                w = int( child['weight'])
            digraph.add_edge(toKeep, child['id'], weight=w)
    return digraph

def create_graph(min_coverage, force):
    run_cmd = cere_configure.cere_config["run_cmd"]
    build_cmd = cere_configure.cere_config["build_cmd"]
    logging.info('Start graph creation')
    if os.path.isfile("{0}/graph.pkl".format(cere_configure.cere_config["cere_measures_path"])):
        if not force:
            logging.info('Keeping previous graph')
            return True

    binary = which(run_cmd)
    if not binary:
        logging.critical("Can't find the binary")
        return False

    profile_file = "{0}/app.prof".format(cere_configure.cere_config["cere_measures_path"])
    if not os.path.isfile(profile_file):
        logging.critical('No profiling file')
        return False

    #regular expression to parse the gperf tool output
    regex_list = [r'(N.*)\s\[label\=\"(.*?)\\n([0-9]*)\s\((.*)\%\)\\rof\s(.*)\s\((.*)\%\)\\r',
                  r'(N.*)\s\[label\=\"(.*)\\n([0-9]*)\s\((.*)\%\)\\r',
                  r'(N.*)\s\-\>\s(N.*)\s\[label\=([0-9]*)\,']

    #Build again the application to be sure we give the right binary to pprof
    try:
        logging.info(subprocess.check_output("{0} MODE=\"original --instrument --instrument-app\" -B".format(build_cmd), stderr=subprocess.STDOUT, shell=True))
    except subprocess.CalledProcessError as err:
        logging.critical(str(err))
        logging.critical(err.output)
        return False
    cmd = subprocess.Popen("pprof -dot --edgefraction={0} {1} {2}".format(min_coverage, binary, profile_file), shell=True, stdout=subprocess.PIPE)

    digraph = nx.DiGraph()
    for line in cmd.stdout:
        matchObj, step = parse_line(regex_list, line)
        if step < 2 :
            digraph = add_node(digraph, matchObj)
        elif step == 2 :
            digraph.add_edge(matchObj.group(1), matchObj.group(2), weight=int(matchObj.group(3)))
        else:
            continue

    cycles = list(nx.simple_cycles(digraph))
    while cycles:
        digraph = remove_cycles(digraph, cycles[0])
        cycles = list(nx.simple_cycles(digraph))

    plot(digraph, 0)
    save_graph(digraph)

    with open("{0}/loops".format(cere_configure.cere_config["cere_measures_path"]), 'w') as f:
        for n, d in digraph.nodes(data=True):
            if d['_valid'] and not d['_small'] and not d['_tested']:
                f.write(d['_name'].replace("extracted", "invivo")+"\n")

    logging.info('Create graph success')
    return True