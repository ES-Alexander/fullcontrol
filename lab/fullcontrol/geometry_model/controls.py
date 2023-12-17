
from typing import Optional
from pydantic import BaseModel


class ModelControls(BaseModel):
    'control to adjust the style of the plot'
    stl_filename: Optional[str] = '3d_model'
    # 'rectangle'/'diamond'/'hexagon'/'octagon'
    shape: Optional[str] = 'rectangle'
    tube_type: Optional[str] = 'flow'  # 'flow'/'cylinders'
    stl_type: Optional[str] = 'ascii'  # 'binary'/'ascii'
    stls_combined: Optional[bool] = True
    # initialization_data is information about initial printing conditions, which may be changed by the fullcontrol 'design', whereas the above attributes are never changed by the 'design'
    # values passed for initialization_data overwrite the default initialization_data of the printer
    initialization_data: Optional[dict] = {}

    def shape_properties(self):
        if self.shape == 'rectangle':
            return (4, 0, True)
        if self.shape == 'diamond':
            return (4, 0, False)
        if self.shape == 'hexagon':
            return (6, 0.5, False)
        if self.shape == 'octagon': return (8, 0.5, True)