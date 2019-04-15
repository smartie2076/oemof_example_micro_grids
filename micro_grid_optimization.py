import os
import pandas as pd

from oemof.tools import logger
import logging

logger.define_logging(screen_level=logging.INFO) #screen_level=logging.DEBUG

from matplotlib import pyplot as plt

import oemof.outputlib as outputlib
import oemof.solph as solph
from oemof.tools import economics


timeindex = pd.date_range('1/1/2017', periods=8760, freq='H')

energysystem = solph.EnergySystem(timeindex=timeindex)
#################################################################
# data
#################################################################

logging.info('Loading timeseries')
full_filename = os.path.join(os.path.dirname(__file__), 'timeseries.csv')
timeseries = pd.read_csv(full_filename, sep=',')

logging.info('Defining costs')

fuel_price_kWh = 0.15 # fuel price in currency/kWh

costs = {'pp_wind': {
             'epc': economics.annuity(capex=1000, n=20, wacc=0.05)},
         'pp_pv': {
             'epc': economics.annuity(capex=750, n=20, wacc=0.05)},
         'pp_diesel': {
             'epc': economics.annuity(capex=300, n=10, wacc=0.05),
             'var': 0},
         'storage': {
             'epc': economics.annuity(capex=300, n=5, wacc=0.05),
             'var': 0}}

#################################################################
# Create oemof object
#################################################################
print('\n')
logging.info('DEFINITION OF OEMOF MODEL:')

logging.info('Electricity bus')
bel = solph.Bus(label='electricity_bus')
energysystem.add(bel)

logging.info('Demand, fixed timeseries')
demand_sink = solph.Sink(label='demand_el',
                         inputs={bel: solph.Flow(actual_value=timeseries['demand_el'],
                                                 fixed=True,
                                                 nominal_value=500)})
energysystem.add(demand_sink)

logging.info('Excess sink')
excess_sink = solph.Sink(label='excess',
                    inputs={bel: solph.Flow()})
energysystem.add(excess_sink)

logging.info('Wind plant with fixed feed-in timeseries')
wind_plant = solph.Source(label='pp_wind',
                          outputs={
                              bel: solph.Flow(nominal_value=None,
                                              fixed=True,
                                              actual_value=timeseries['wind'],
                                              investment=solph.Investment(
                                                  ep_costs=costs['pp_wind']['epc']))})
energysystem.add(wind_plant)

logging.info('PV plant with fixed feed-in timeseries')
pv_plant = solph.Source(label='pp_pv',
                        outputs={
                            bel: solph.Flow(nominal_value=None,
                                            fixed=True,
                                            actual_value=timeseries['pv'],
                                            investment=solph.Investment(
                                                ep_costs=costs['pp_wind']['epc']))})

energysystem.add(pv_plant)

logging.info('Diesel fuel bus, source and transformer')
bfuel = solph.Bus(label='fuel_bus')

fuel_source = solph.Source(label='diesel',
       outputs={
           bfuel: solph.Flow(nominal_value=None,
                     variable_costs=fuel_price_kWh,
                     )}
       )

genset = solph.Transformer(label="transformer_genset",
                           inputs={bfuel: solph.Flow()},
                           outputs={bel: solph.Flow(
                               variable_costs=costs['pp_diesel']['var'],
                               investment=solph.Investment(
                                   ep_costs=costs['pp_diesel']['epc']))},
                           conversion_factors={bel: 0.33}
                           )
energysystem.add(bfuel, fuel_source, genset)

logging.info('Battery storage')
storage = solph.components.GenericStorage(
    label='storage',
    inputs={
        bel: solph.Flow()},
    outputs={
        bel: solph.Flow()},
    capacity_loss=0.00,
    initial_capacity=0.5, # or None
    invest_relation_input_capacity=1/5,
    invest_relation_output_capacity=1,
    inflow_conversion_factor=0.95,
    outflow_conversion_factor=0.95,
    investment=solph.Investment(ep_costs=costs['storage']['epc']))

energysystem.add(storage)
#################################################################
# Create model and solve
#################################################################
print('\n')
logging.info('Initializing model')
m = solph.Model(energysystem)

# om.write(filename, io_options={'symbolic_solver_labels': True})

logging.info('Starting oemof-optimization of capacities')
m.solve(solver='cbc', solve_kwargs={'tee': False})

logging.info('Processing results')
results = outputlib.processing.results(m)

print('\n')
logging.info('Plot flows on electricity bus')
outputlib.views.node(results, 'electricity_bus')['sequences'].plot(drawstyle='steps')
plt.show()

logging.info('Get optimized capacities')
el_bus = outputlib.views.node(results, 'electricity_bus')
cap_storage = el_bus['scalars'][(('electricity_bus', 'storage'), 'invest')]/(1/5) # Divided by c-rate charge
cap_wind = el_bus['scalars'][(('pp_wind', 'electricity_bus'), 'invest')]
cap_pv = el_bus['scalars'][(('pp_pv', 'electricity_bus'), 'invest')]
cap_genset = el_bus['scalars'][(('transformer_genset', 'electricity_bus'), 'invest')]

logging.info('Capacities optimized: Storage (' + str(cap_storage)
             + '), Wind (' + str(cap_wind)
             + '), PV (' + str(cap_pv)
             + '), Genset (' + str(cap_genset) + ').')