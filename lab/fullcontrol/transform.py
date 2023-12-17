
# # import functions and classes that will be accessible to the user
# from .classes import *
# from fullcontrol.common import check, flatten, linspace, export_design, import_design, points_only, relative_point, first_point
from lab.fullcontrol.geometry_model.controls import ModelControls


def transform(steps: list, result_type: str, controls: ModelControls = None):
    '''transform a fullcontrol design (a list of function class instances) into result_type
    "3d_model". Optionally, ModelControls can be passed to control how the 3d_model is generated.
    '''

    if result_type == '3d_model':  # this line of code is currently redundant but maintained to be consistent with fullcontrol.combinations.gcode_and_visualization.common in any future expansion to the results_types here
        from lab.fullcontrol.geometry_model.steps2geometry import geometry_model
        if controls != None:
            return geometry_model(steps, controls)
        else:
            return geometry_model(steps)
