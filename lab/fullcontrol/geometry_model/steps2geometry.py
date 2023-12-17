
from lab.fullcontrol.geometry_model.controls import ModelControls
from fullcontrol.visualize.controls import PlotControls


def reuse_visualize(steps: list, model_controls: ModelControls):
    from fullcontrol.visualize.state import State
    from fullcontrol.visualize.plot_data import PlotData

    plot_controls = PlotControls(tube_type=model_controls.tube_type,
                                 initialization_data=model_controls.initialization_data)
    state = State(steps, plot_controls)
    plot_data = PlotData(steps, state)
    for step in steps:
        step.visualize(state, plot_data, plot_controls)
    plot_data.cleanup()
    return plot_data


def geometry_model(steps: list, model_controls: ModelControls = ModelControls()):
    ''' use the existing visualize function to get plot_data that is normally used to generate 
    the 3D model for visualization and is used here to generate the 3D model for stl output or similar
    '''
    from fullcontrol.visualize.plotly import plot
    from fullcontrol.visualize.controls import PlotControls
    plot_controls = PlotControls(tube_type=model_controls.tube_type,
                                 initialization_data=model_controls.initialization_data)

    plot_data = reuse_visualize(steps, plot_controls)
    plot(plot_data, model_controls)
