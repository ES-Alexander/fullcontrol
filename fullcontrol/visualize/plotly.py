import numpy as np
import plotly.graph_objects as go
from fullcontrol.visualize.plot_data import PlotData
from fullcontrol.visualize.controls import PlotControls
from fullcontrol.visualize.tube_mesh import CylindersMesh, FlowTubeMesh, MeshExporter

import numpy as np
import plotly.graph_objects as go
from fullcontrol.visualize.plot_data import PlotData
from fullcontrol.visualize.controls import PlotControls
from fullcontrol.visualize.tube_mesh import CylindersMesh, FlowTubeMesh, MeshExporter

from lab.fullcontrol.geometry_model.controls import ModelControls


def generate_mesh(path, controls: PlotControls, linewidth_now: float, Mesh: FlowTubeMesh):
    global local_max, saving_stl
    path_points = np.array([path.xvals, path.yvals, path.zvals]).T
    good_points = np.ones(len(path_points), dtype=bool)
    dups = np.all(np.diff(path_points, axis=0) == 0, axis=1)
    if np.any(dups):
        # remove successive duplicate points so TubeMesh can be generated
        good_points[1:] = ~dups
        colors_now = np.array(colors_now, dtype=object)[good_points]
    path_points = path_points[good_points]
    num_path_points = len(path_points)
    # neat = bool(controls.neat_for_publishing)
    # capped = neat or num_path_points < 100
    capped = False
    widths = path.widths
    if not widths:  # why does this exist? surely the design must dictate the widths of all lines
        local_max = widths = linewidth_now/10
    else:
        widths = np.array(widths)[good_points]
        if Mesh == CylindersMesh:
            widths = widths[1:]
        local_max = max(widths)
    heights = path.heights or None
    if heights:
        heights = np.array(heights)[good_points]
        if Mesh == CylindersMesh:
            heights = heights[1:]
    if saving_stl:
        sides, rounding_strength, flat_sides = controls.shape_properties()
    else:
        # if automatic, dynamically reduce the number of sides when plotting large numbers of path points
        sides = 6 if num_path_points < 10 else 4 if num_path_points < 1_000_000 else 2
        rounding_strength, flat_sides = 1, True
    return Mesh(path_points, widths=widths, heights=heights, sides=sides, capped=capped, inplace_path=True, rounding_strength=rounding_strength, flat_sides=flat_sides)


def plot(data: PlotData, controls: PlotControls):
    'plot data for x y z lines with RGB colors and annotations. style of plot governed by controls'

    # if True, this function was passed a ModelControls object (for stl output as similar) instead of a PlotControls
    global saving_stl
    saving_stl = bool(isinstance(controls, ModelControls))
    if controls.tube_type is None:
        Mesh = FlowTubeMesh
    else:
        Mesh = {'flow': FlowTubeMesh, 'cylinders': CylindersMesh}[
            controls.tube_type]

    if saving_stl:
        # generate stl output(s) but no plot
        meshes = []
        for path in data.paths:
            # linewidth_now = controls.line_width * 2 if path.extruder.on == True else controls.line_width*0.5
            if path.extruder.on:
                # meshes.append(generate_mesh(path, controls, linewidth_now, Mesh))
                meshes.append(generate_mesh(path, controls, 0, Mesh))
        binary_file = controls.stl_type.lower() == 'binary'
        MeshExporter({'name': 'extrusion'}, meshes).to_stl(
            controls.stl_filename + '.stl', binary_file, combined_file=controls.stls_combined)
    else:
        # generate plots
        fig = go.Figure()

        if controls.style is None:
            print('Plot shows printed line width - use `fc.PlotControls(style="line")` for a simple path, or'
                  ' `fc.PlotControls(style="tube")` to disable this message.')
            controls.style = 'tube'

        # any_mesh_plots = False
        max_width = 0
        for path in data.paths:
            colors_now = [
                f'rgb({color[0]*255:.2f}, {color[1]*255:.2f}, {color[2]*255:.2f})' for color in path.colors]
            linewidth_now = controls.line_width * \
                2 if path.extruder.on == True else controls.line_width*0.5
            if path.extruder.on and controls.style == 'tube':
                mesh = generate_mesh(path, controls, linewidth_now, Mesh)
                fig.add_trace(mesh.to_Mesh3d(colors=colors_now))
                # any_mesh_plots = True
                max_width = max(max_width, local_max)
            elif not controls.hide_travel or path.extruder.on:  # plot travel lines for tube and line
                if not saving_stl:
                    fig.add_trace(go.Scatter3d(mode='lines', x=path.xvals, y=path.yvals, z=path.zvals,
                                               showlegend=False, line=dict(width=linewidth_now, color=colors_now)))

        # find a bounding box, to create a plot with equally proportioned X Y Z scales (so a cuboid looks like a cuboid, not a cube)
        bounding_box_size = max(data.bounding_box.maxx-data.bounding_box.minx, data.bounding_box.maxy -
                                data.bounding_box.miny, data.bounding_box.maxz-min(0, data.bounding_box.minz))
        bounding_box_size += 0.002
        bounding_box_size += max_width

        # generate annotations
        annotations_pts = []
        annotations = []
        if controls.hide_annotations == False and not controls.neat_for_publishing:
            for annotation in data.annotations:
                x, y, z = (annotation[axis] for axis in 'xyz')
                annotations_pts.append([x, y, z])
                annotations.append(dict(
                    showarrow=False,
                    x=x, y=y, z=z,
                    text=annotation['label'],
                    yshift=10))
            xs, ys, zs = zip(*annotations_pts) if annotations_pts else [[]]*3
            fig.add_trace(go.Scatter3d(mode='markers', x=xs, y=ys, z=zs,
                                       showlegend=False, marker=dict(size=2, color='red')))

            # make sure the bounding box is big enough for the annotations
            # the 0.001 is to make sure the annotations don't lie on the boundary
            midx, midy, midz = (
                getattr(data.bounding_box, f'mid{axis}') for axis in 'xyz')
            offset = 0.001
            offset_both_sides = 2 * offset
            for (x, y, z) in annotations_pts:
                if x < midx - bounding_box_size / 2 + offset:
                    bounding_box_size = 2 * (midx - x) + offset_both_sides
                if x > midx + bounding_box_size / 2 - offset:
                    bounding_box_size = 2 * (x - midx) + offset_both_sides
                if y < midy - bounding_box_size / 2 + offset:
                    bounding_box_size = 2 * (midy - y) + offset_both_sides
                if y > midy + bounding_box_size / 2 - offset:
                    bounding_box_size = 2 * (y - midy) + offset_both_sides
                if z < midz - bounding_box_size / 2 + offset:
                    bounding_box_size = 2 * (midz - z) + offset_both_sides
                if z > midz + bounding_box_size / 2 - offset:
                    bounding_box_size = 2 * (z - midz) + offset_both_sides

        camera = dict(eye=dict(x=-0.5/controls.zoom, y=-1/controls.zoom, z=-0.5+0.5/controls.zoom),
                      center=dict(x=0, y=0, z=-0.5))
        fig.update_layout(template='plotly_dark', paper_bgcolor="black", scene_aspectmode='cube', scene=dict(annotations=annotations,
                                                                                                             xaxis=dict(backgroundcolor="black", nticks=10, range=[
                                                                                                                 data.bounding_box.midx-bounding_box_size/2, data.bounding_box.midx+bounding_box_size/2],),
                                                                                                             yaxis=dict(backgroundcolor="black", nticks=10, range=[
                                                                                                                 data.bounding_box.midy-bounding_box_size/2, data.bounding_box.midy+bounding_box_size/2],),
                                                                                                             zaxis=dict(backgroundcolor="black", nticks=10, range=[min(0, data.bounding_box.minz), bounding_box_size],),),
                          scene_camera=camera,
                          width=800, height=500, margin=dict(l=10, r=10, b=10, t=10, pad=4))
        if controls.hide_axes or controls.neat_for_publishing:
            for axis in ['xaxis', 'yaxis', 'zaxis']:
                fig.update_layout(
                    scene={axis: dict(showgrid=False, zeroline=False, visible=False)})
        if controls.neat_for_publishing:
            fig.update_layout(width=500, height=500)
        fig.show()
