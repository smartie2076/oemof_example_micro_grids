import os
import pandas as pd

from oemof.tools import logger
import logging

logger.define_logging(screen_level=logging.INFO) #screen_level=logging.DEBUG

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

logging.info('Loading timeseries')
full_filename = os.path.join(os.path.dirname(__file__), 'timeseries.csv')
timeseries = pd.read_csv(full_filename, sep=',')

logging.info('Defining costs')
costs = {'pp_wind': {
             'epc': economics.annuity(capex=1000, n=20, wacc=0.05)},
         'pp_pv': {
             'epc': economics.annuity(capex=750, n=20, wacc=0.05)},
         'pp_diesel': {
             'epc': economics.annuity(capex=300, n=10, wacc=0.05),
             'var': 30},
         'pp_bio': {
             'epc': economics.annuity(capex=1000, n=10, wacc=0.05),
             'var': 50},
         'storage': {
             'epc': economics.annuity(capex=1500, n=10, wacc=0.05),
             'var': 0}}

#################################################################
# Create oemof object
#################################################################

logging.info('\n DEFINITION OF OEMOF MODEL:')

logging.info('Electricity bus')
bel = Bus(label='micro_grid')

logging.info('Excess sink')
Sink(label='excess',
     inputs={bel: Flow(variable_costs=10e3)})

logging.info('Wind plant with fixed feed-in timeseries')
Source(label='pp_wind',
       outputs={
           bel: Flow(nominal_value=None, fixed=True,
                     actual_value=timeseries['wind'],
                     investment=Investment(ep_costs=costs['pp_wind']['epc']))})

logging.info('PV plant with fixed feed-in timeseries')
Source(label='pp_pv',
       outputs={
           bel: Flow(nominal_value=None, fixed=True,
                     actual_value=timeseries['pv'],
                     investment=Investment(ep_costs=costs['pp_wind']['epc']))})

logging.info('Diesel fuel source')
Source(label='pp_diesel',
       outputs={
           bel: Flow(nominal_value=None,
                     variable_costs=costs['pp_diesel']['var'],
                     investment=Investment(ep_costs=costs['pp_diesel']['epc']))}
       )

logging.info('Bio fuel source')
Source(label='pp_bio',
       outputs={
           bel: Flow(nominal_value=None,
                     variable_costs=costs['pp_bio']['var'],
                     summed_max=300e3,
                     investment=Investment(ep_costs=costs['pp_bio']['epc']))})

logging.info('Demand, fixed timeseries')
Sink(label='demand_el',
     inputs={
         bel: Flow(actual_value=timeseries['demand_el'],
                   fixed=True, nominal_value=500)})

logging.info('Battery storage')
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

logging.info('\n Initializing model')
m = Model(energysystem)

# om.write(filename, io_options={'symbolic_solver_labels': True})

logging.info('Starting oemof-optimization of capacities')
m.solve(solver='cbc', solve_kwargs={'tee': False})

logging.info('Processing results')
results = processing.results(m)

views.node(results, 'micro_grid')['sequences'].plot(drawstyle='steps')

plt.show()