# -*- coding: utf-8 -*-
"""
General description
-------------------
Based on example from the SDEWES conference paper:

Simon Hilpert, Cord Kaldemeyer, Uwe Krien, Stephan Günther (2017).
'Solph - An Open Multi Purpose Optimisation Library for Flexible
         Energy System Analysis'. Paper presented at SDEWES Conference,
         Dubrovnik.

Data
----
timeseries.csv

Installation requirements
-------------------------
This example requires the latest version of oemof and others. Install by:

    pip install oemof matplotlib

"""

import os
import pandas as pd
from matplotlib import pyplot as plt

from oemof.network import Node
from oemof.outputlib import processing, views
from oemof.solph import (EnergySystem, Bus, Source, Sink, Flow,
                         Model, Investment, components)
from oemof.tools import economics


timeindex = pd.date_range('1/1/2017', periods=8760, freq='H')

energysystem = EnergySystem(timeindex=timeindex)
Node.registry = energysystem
#################################################################
# data
#################################################################
# Read data file
full_filename = os.path.join(os.path.dirname(__file__),
                             'timeseries.csv')

timeseries = pd.read_csv(full_filename, sep=',')

costs = {'pp_wind': {
             'cap': 500},
         'pp_pv': {
             'cap': 200},
         'pp_diesel': {
             'cap': 1500,
             'var': 30},
         'pp_bio': {
             'cap': 300,
             'var': 50},
         'storage': {
             'cap': 800}}

#################################################################
# Create oemof object
#################################################################

bel = Bus(label='micro_grid')

Sink(label='excess',
     inputs={bel: Flow(variable_costs=10e3)})

Source(label='pp_wind',
       outputs={
           bel: Flow(nominal_value=None, fixed=True,
                     actual_value=timeseries['wind'],
                     investment=Investment(ep_costs=costs['pp_wind']['epc']))})

Source(label='pp_pv',
       outputs={
           bel: Flow(nominal_value=None, fixed=True,
                     actual_value=timeseries['pv'],
                     investment=Investment(ep_costs=costs['pp_wind']['epc']))})

Source(label='pp_diesel',
       outputs={
           bel: Flow(nominal_value=None,
                     variable_costs=costs['pp_diesel']['var'],
                     investment=Investment(ep_costs=costs['pp_diesel']['epc']))}
       )

Source(label='pp_bio',
       outputs={
           bel: Flow(nominal_value=None,
                     variable_costs=costs['pp_bio']['var'],
                     summed_max=300e3,
                     investment=Investment(ep_costs=costs['pp_bio']['epc']))})

Sink(label='demand_el',
     inputs={
         bel: Flow(actual_value=timeseries['demand_el'],
                   fixed=True, nominal_value=500)})

components.GenericStorage(
    label='storage',
    inputs={
        bel: Flow()},
    outputs={
        bel: Flow()},
    capacity_loss=0.00,
    initial_capacity=0.5,
    invest_relation_input_capacity=1/6,
    invest_relation_output_capacity=1/6,
    inflow_conversion_factor=0.95,
    outflow_conversion_factor=0.95,
    investment=Investment(ep_costs=costs['storage']['epc']))

#################################################################
# Create model and solve
#################################################################

m = Model(energysystem)

# om.write(filename, io_options={'symbolic_solver_labels': True})

m.solve(solver='cbc', solve_kwargs={'tee': False})

results = processing.results(m)

views.node(results, 'storage')

views.node(results, 'micro_grid')['sequences'].plot(drawstyle='steps')

plt.show()