
from typing import Optional
from pydantic import BaseModel


class ModelControls(BaseModel):
    'control to adjust the style of the plot'
    stl_filename: Optional[str] = '3d_model'
    include_date: Optional[bool] = True
    tube_shape: Optional[str] = 'rectangle'  # 'rectangle'/'diamond'/'hexagon'/'octagon'
    tube_type: Optional[str] = 'flow'  # 'flow'/'cylinders'
    stl_type: Optional[str] = 'ascii'  # 'binary'/'ascii'
    stls_combined: Optional[bool] = True
    # initialization_data is information about initial printing conditions, which may be changed by the fullcontrol 'design', whereas the above attributes are never changed by the 'design'
    # values passed for initialization_data overwrite the default initialization_data of the printer
    initialization_data: Optional[dict] = {}

    def shape_properties(self):
        if self.tube_shape == 'rectangle':
            return (4, 0, True)
        if self.tube_shape == 'diamond':
            return (4, 1, False)
        if self.tube_shape == 'hexagon':
            return (6, 0.4, False)
        if self.tube_shape == 'octagon':
            return (8, 0.4, True)
