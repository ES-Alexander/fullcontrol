# relevant types
from collections.abc import Sequence
from numbers import Real
import pathlib
import math
# functionality
import struct
from datetime import datetime
from itertools import chain, pairwise
import plotly.graph_objects as go
import numpy as np


class MeshExporter:
    def __init__(self, metadata: dict | None = None,
                 bodies: list | None = None):
        self.metadata = metadata or {} # default to empty dictionary
        self._bodies = bodies or [self]

    @property
    def triangle_points(self):
        return NotImplemented

    @property
    def mesh_normals(self):
        ''' Assumes `triangle_indices` are defined anti-clockwise. '''
        if (cached := getattr(self, '_mesh_normals', None)) is not None:
            return cached
        triangle_points = self.triangle_points
        # anticlockwise point order when viewed from outside
        first_vectors = triangle_points[1::3] - triangle_points[::3]
        second_vectors = triangle_points[2::3] - triangle_points[::3]
        self._mesh_normals = np.cross(first_vectors, second_vectors)
        return self._mesh_normals

    def to_stl(self, path: pathlib.Path | str, binary: bool = True,
               overwrite: bool = False, combined_file: bool = True):
        write_header = self._write_binary_stl_header if binary else lambda out: None
        write_data = self._write_binary_stl_data if binary else self._write_ascii_stl_data

        path = pathlib.Path(path)
        name = self.metadata.get('name', path.stem)
        num_bodies = len(self._bodies)
        # Calculate digits needed for zero-padding increments
        digits = math.ceil(math.log10(num_bodies)) + 1
        mode = 'w' + 'b'*binary
        if combined_file or num_bodies == 1:
            if num_bodies > 1:
                print("WARNING! Multi-object STL file - may not work in some softwares, nor with stl_type='binary'")

            # with self.valid_path(path, overwrite).open(mode) as out:
            # file_path = path.with_stem(
            #     f'{path.stem}__{datetime.today().strftime("%d-%m-%Y__%H-%M-%S")}')
            file_path = path
            with file_path.open(mode) as out:
                write_header(out)
                for index, body in enumerate(self._bodies):
                    identifier = (
                        index if binary
                        else (name if num_bodies == 1 else f'{name}_{index:>0{digits}}')
                    )
                    write_data(out, body.mesh_normals,
                               body.triangle_points.reshape(-1,9), identifier)
        else:
            for index, body in enumerate(self._bodies):
                # file_path = self.valid_path(path.with_stem(f'{path.stem}_{index:>0{digits}}'),overwrite)
                # file_path = path.with_stem(
                #     f'{path.stem}_{index:>0{digits}}__{datetime.today().strftime("%d-%m-%Y__%H-%M-%S")}')
                file_path = path
                with file_path.open(mode) as out:
                    identifier = 0 if binary else name
                    write_header(out)
                    write_data(out, body.mesh_normals,
                               body.triangle_points.reshape(-1,9), identifier)

    @staticmethod
    def _write_ascii_stl_data(out, mesh_normals, triangle_points, solid_name: str = 'object'):
        print(f'solid {solid_name} # Generated by FullControlXYZ', file=out)
        for n, vs in zip(mesh_normals, triangle_points):
            print(
                f'facet normal {n[0]:e} {n[1]:e} {n[2]:e}',
                 '    outer loop',
                f'        vertex {vs[0]:e} {vs[1]:e} {vs[2]:e}',
                f'        vertex {vs[3]:e} {vs[4]:e} {vs[5]:e}',
                f'        vertex {vs[6]:e} {vs[7]:e} {vs[8]:e}',
                 '    endloop',
                 'endfacet',
                sep='\n', file=out)
        print(f'endsolid {solid_name}', file=out)

    def _write_binary_stl_header(self, out):
        UNITS = self.metadata.get('units', 'mm')
        AUTHOR = self.metadata.get('author', None)
        author = f'{AUTHOR=},' if AUTHOR is not None else ''

        header = bytearray([0]*80)
        # header is arbitrary, but put some meaningful data into it
        #  TODO: support optional COLOR and MATERIAL fields
        #    'COLOR' should be a 4-byte RGBA value, as a simple full-object color
        #    'MATERIAL' should be diffuse reflection, specular highlight, ambient light
        #      as 4-byte RGBA values - preferred over COLOR
        header_data = f'STL,{UNITS=},{author}SOFTWARE=FullControlXYZ'.encode('utf-8')
        header[:len(header_data)] = header_data
        out.write(header[:80]) # ensure header is valid

    @staticmethod
    def _write_binary_stl_data(out, mesh_normals, triangle_points, solid_index: int = 0):
        num_triangles = len(triangle_points) # one triangle per data row
        if solid_index == 0:
            out.write(struct.pack('<I', num_triangles))

        attribute_byte_count = solid_index or 0 # TODO: support facet color options
        # Create a structured array in the STL binary format
        out_data = np.empty(num_triangles, dtype=[
            *((f'n{axis}', 'f4') for axis in 'xyz'),
            *((f'v{vertex}{axis}', 'f4') for vertex in '123' for axis in 'xyz'),
            ('attrib','u2')
        ])
        # Copy across the data
        for index, axis in enumerate('xyz'):
            out_data[f'n{axis}'] = mesh_normals[:, index]
            for vi, vertex in enumerate('123'):
                out_data[f'v{vertex}{axis}'] = triangle_points[:, vi*3+index]
        out_data['attrib'] = attribute_byte_count
        # Dump it to the output file
        out_data.tofile(out)
        # TODO compare timing (and memory usage?) for large meshes
        #  Numpy approach expected to be much faster than looping + struct packing
        #for n, vs in zip(mesh_normals, triangle_points):
        #    out.write(struct.pack('<'+'f'*(3*(1+3))+'H', *n, *vs, attribute_byte_count))

    # @staticmethod
    # def valid_path(path: pathlib.Path | str, overwrite: bool = False) -> pathlib.Path:
    #     path = pathlib.Path(path) # ensure a valid Path object
    #     if not overwrite and path.is_file():
    #         path = path.with_stem(
    #             f'{path.stem}__{datetime.today().strftime("%d-%m-%Y__%H-%M-%S")}'
    #         )
    #     return path


class TubeMesh(MeshExporter):
    ''' A triangle mesh of conical tubes that follow a path of points. '''
    def __init__(
            self,
            path: np.ndarray | Sequence,
            widths: Real | np.ndarray | Sequence,
            heights: Real | np.ndarray | Sequence,
            *, # make remaining arguments keyword-only
            sides: int,
            rounding_strength: float,
            flat_sides: bool,
            capped: bool,
            inplace_path: bool,
            metadata: dict | None = None,
    ):
        '''
        `path` should contain N points to 'draw' a tube along.
            Points are 3D (x,y,z), but if specified as 2D will assume z=0.
            Successive points are expected to be distinct (i.e. x[i] != x[i+1]).
              If this cannot be guaranteed, use the `from_raw_path` constructor.
        `widths` should be either
            - a single numerical value that applies to all points,
            - N numbers denoting the diameter at each path point/corner
        `heights` is like `widths`.
            If left as `None`, uses the `widths` value.
        `sides` determines the number of sides rendered for each tube.
            Fewer sides render faster but form a rougher cross-section approximation.
            When set to an even number, the dimension between flat horizontal and/or
            vertical sides is expanded such that the sides are flat against the 
            specified segment width/height as appropriate.
            Must be >= 2. Default 4.
        `rounding_strength` determines whether the cross-section profile is
            rectangular (0), elliptical (1), or somewhere in between.
            Should generally be left at 1 unless sides >= 6, although for an exact
            rectangle it's fine to use sides = 4.
        `flat_sides` rotates the sample angles of the cross-section profile such
            that if `sides` is a multiple of 2 the vertical sides will be flat,
            and if `sides` is a multiple of 4 the horizontal sides will also be flat.
            If `flat_sides` is set to False then the major and minor axis points will
            be exactly the specified width and height, but horizontal or vertical
            touching between tubes will be along a line instead of a full surface.
        `capped` is a flag specifying whether to generate triangles for a cap on
            each end of the path. Off by default, but useful for generating closed
            meshes (e.g. for an STL).
        `inplace_path` is a flag specifying that `path` is already a valid numpy
            array of 3D points with float values, and will not be changed externally
            so can safely be used directly (instead of via a copy).
        `metadata` is a dictionary of metadata relevant to the input path.
        '''
        super().__init__(metadata)
        self.path_points = path if inplace_path else self.make_valid_path(path)

        self.num_cylinders = len(path) - 1
        self.radial_widths = np.reshape(widths, (-1,1)) / 2
        self.radial_heights = np.reshape(heights, (-1,1)) / 2 if heights is not None \
            else self.radial_widths
        self.sides = sides
        self.rounding_strength = rounding_strength
        self.flat_sides = flat_sides
        self.capped = capped

        self.__init_mesh_points()
        self.__init_triangles()
        if self.capped:
            self.__init_endcaps()

    def __init_mesh_points(self):
        corner_tangents = self.calculate_corner_tangents(self.path_points)

        # Determine path-aligned point offsets from normal vectors
        sway_offsets, heave_offsets = self.calculate_normals(corner_tangents)
        # Normalise, then scale by user-specified dimensions
        sway_offsets /= np.linalg.norm(sway_offsets, axis=1, keepdims=True)
        sway_offsets *= self.radial_widths
        heave_offsets /= np.linalg.norm(heave_offsets, axis=1, keepdims=True)
        heave_offsets *= self.radial_heights

        point_offsets = self.calculate_point_offsets(sway_offsets, heave_offsets)

        mesh_points = self.path_points[..., np.newaxis] + point_offsets
        # rearrange and reshape into a simple array of points
        self.mesh_points = mesh_points.swapaxes(1,2).reshape(-1,3)

    def calculate_point_offsets(self, sway_offsets, heave_offsets):
        '''
        Converts the path point sway and heave offset vectors into offset points.

        Returns a depth-stacked array of shape (len(self.path_points), 3, self.sides),
          where each row represents the cross-section profile offset points for a
          single point on the tube trajectory.

        Can be overridden via inheritance or monkey-patching to change the generated
          cross-section profile.
        '''
        scale = 2 * np.pi / self.sides
        # correction factors to expand flat_sides cases out to full width/height as relevant
        sway_expand = heave_expand = 1
        if self.flat_sides and self.sides % 2 == 0: # vertical sides are flat
            sway_expand = 1 / abs(math.cos(scale * (0 + 1/2))**self.rounding_strength)
            if self.sides % 4 == 0: # top and bottom are also flat
                heave_expand = sway_expand
        elif self.sides % 2 == 0: # only top and bottom are flat
            heave_expand = 1 / abs(math.sin(scale * (self.sides // 4))**self.rounding_strength)

        # Combine with even proportions around the cross-section profile
        # NOTE: there's potential for optimisation here, if we want to add
        #  special cases for 2/4/... sided tubes, to reduce operations.
        point_offsets = []
        for s in range(self.sides):
            s += self.flat_sides / 2
            # use math functions here because numpy datatypes don't fall gracefully to complex
            sway_mult = math.cos(s*scale)
            heave_mult = math.sin(s*scale)
            # support super-ellipse (rounded-rectangle) cross-section
            if self.rounding_strength != 1:
                # take abs to get magnitude of complex value (due to fractional power)
                sway_mult = np.sign(sway_mult) * abs(sway_mult ** self.rounding_strength) * sway_expand
                heave_mult = np.sign(heave_mult) * abs(heave_mult ** self.rounding_strength) * heave_expand
            point_offsets.append(sway_mult*sway_offsets + heave_mult*heave_offsets)
        return np.dstack(point_offsets)

    def __init_triangles(self):
        self.triangles = self.generate_tube_triangles(self.sides, self.num_cylinders)

    def __init_endcaps(self):
        # Add in the endpoints to cap the tube ends
        #  appending numpy arrays is a poor use of memory,
        #  but I'm not sure what would be better here
        self.mesh_points = np.append(self.mesh_points,
                                     [self.path_points[0], self.path_points[-1]], axis=0)
        path_start, path_end = len(self.mesh_points) - np.array([2,1])

        cap_triangles = []
        for step, (index_offset, path_point) in enumerate(
                ((0, path_start),
                 (self.num_cylinders*self.sides, path_end))
            ):
            # flip end endcap triangles for correct orientation (anticlockwise point order)
            step = -(step * 2 - 1) # 1 for start, -1 for end
            cap_triangles.append([
                [first+index_offset, second+index_offset, path_point][::step]
                for first, second in pairwise(chain(range(self.sides),(0,)))
            ])

        # triangle definition order matters for rendering purposes
        self.triangles = np.vstack((cap_triangles[0], self.triangles, cap_triangles[1]))

    @staticmethod
    def make_valid_path(path):
        path_dims = len(path[0])
        path_points = np.empty((len(path), 3))
        path_points[:,:path_dims] = path
        if path_dims == 2: # zero-pad z-axis if necessary
            path_points[:,2] = 0
        return path_points

    @staticmethod
    def calculate_corner_tangents(path_points):
        # Calculate path segment direction vectors
        corner_tangents = np.empty_like(path_points)
        corner_tangents[:-1] = path_points[1:] - path_points[:-1]
        # Set the last point to have the same direction as its segment
        corner_tangents[-1] = corner_tangents[-2]
        # Normalise directions to avoid tangents being scaled by segment lengths
        corner_tangents /= np.linalg.norm(corner_tangents, axis=1, keepdims=True)
        # Convert into path-oriented corner tangent vectors
        corner_tangents[1:-1] += corner_tangents[0:-2]
        return corner_tangents

    @staticmethod
    def calculate_normals(corner_tangents):
        # Calculate normals in the sway direction, for a boat balancing on the path
        #  path:(1,0,0) -> sway_normal:(0,-1,0)
        #  path:(0,1,0) -> sway_normal:(1,0,0)
        sway_normals = np.cross(corner_tangents, [0,0,1]) # cross w/ unit z vector
        # Override vertically upwards tangents to have rightwards (+x) sway normals
        #  and vertically downwards paths to have leftwards (-x) sway normals
        # Override necessary because cross product returns 0,0,0 for aligned vectors
        z_lines = (corner_tangents[:,:2] == [0,0]).all(axis=1)
        sway_normals[z_lines] = [1,0,0] # overide to unit x vector

        # Find sequential sway_normals pointing in opposite directions
        #  uses signs of the dot products of each vector pair in the array
        #  this einsum is for vectorised dot-products: (a*b).sum(axis=1)
        twisted_tubes = \
            np.sign(np.einsum('ij,ij->i', sway_normals[1:], sway_normals[:-1])) == -1
        # Flip as appropriate
        # NOTE: does not fix any 90 degree offsets
        #  This is _possible_, but annoying to detect, and the smoothest result
        #  would come from swapping sway and heave normals (also annoying to do)
        angle_adjustment = np.ones((len(sway_normals),1))
        angle_adjustment[1:][twisted_tubes] = -1
        # use cumulative product, because flipping one should also flip all
        #  the ones after it, to avoid just causing a twist in the next section
        angle_adjustment = np.cumprod(angle_adjustment, axis=0)
        sway_normals *= angle_adjustment

        # Calculate normals in the heave direction
        #  path:(1,0,0) -> heave_normal:(0,0,1)
        heave_normals = np.cross(sway_normals, corner_tangents)

        return sway_normals, heave_normals

    @classmethod
    def generate_tube_triangles(cls, sides, num_cylinders):
        return (
            cls.generate_cylinder_triangles(sides)[..., np.newaxis]
            .repeat(num_cylinders, axis=2)
            + np.arange(num_cylinders) * sides
        ).swapaxes(0,1).swapaxes(0,2).reshape(-1,3)

    @staticmethod
    def generate_cylinder_triangles(sides):
        return np.array(list(
            chain.from_iterable(
                # anticlockwise point order when viewed from outside
                [[first, sides+first, second],
                 [second, sides+first, sides+second]]
                for first, second in pairwise(chain(range(sides),(0,)))
            )
        ))

    @property
    def triangle_points(self):
        ''' An array of the mesh points for each index of each triangle. '''
        if (cached := getattr(self, '_triangle_points', None)) is not None:
            return cached
        self._triangle_points = self.mesh_points[self.triangles.flatten()]
        return self._triangle_points

    def to_stl(self, path: pathlib.Path | str, **kwargs):
        if not self.capped:
            print('WARNING! Non-manifold mesh - not using capped ends.')
        super().to_stl(path, **kwargs)

    def to_Mesh3d(
            self,
            colors: np.ndarray | list[Real | str] | str | None = None,
            **mesh_kwargs
    ) -> go.Mesh3d:
        '''
        `colors` should be either
            - `None` (to use self.metadata / plotly's default / configure elsewhere)
            - a single color for all the tubes,
            - N colors denoting the color of each path point (with blends between),
            - N-1 colors denoting the (constant) color of each tube
            - N+1 colors denoting the color of each tube + the endcaps
                -> Only applicable if the mesh was generated with `capped`=True
            Each color can be either
                - A hex string (e.g. '#ff0000')
                - An rgb/rgba string (e.g. 'rgb(255,0,0)'/'rgba(0,255,255,0.3)')
                - An hsl/hsla string (e.g. 'hsl(0,100%,50%)')
                - An hsv/hsva string (e.g. 'hsv(0,100%,100%)')
                - A named CSS color
                - A number that will be interpreted as a color
                 according to mesh3d.colorscale
        '''
        mesh_kwargs = mesh_kwargs.copy()
        # default to stored metadata (if available)
        if colors is None:
            colors = self.metadata.get('colors')

        # turn path colors into appropriate mesh colors
        if colors is None or isinstance(colors, str):
            mesh_kwargs['color'] = colors
        elif len(colors) == len(self.path_points):
            colors = np.repeat(colors, self.sides, axis=0)
            if self.capped:
                colors = np.hstack((colors, colors[0], colors[-1]))
            mesh_kwargs['vertexcolor'] = colors
        elif len(colors) == self.num_cylinders:
            colors = np.repeat(colors, self.sides*2, axis=0)
            if self.capped:
                colors = np.hstack((colors[:self.sides], colors, colors[-self.sides:]))
            mesh_kwargs['facecolor'] = colors
        elif len(colors) == self.num_cylinders+2:
            colors = np.repeat(colors, self.sides*2, axis=0)[self.sides:-self.sides]
            mesh_kwargs['facecolor'] = colors

        return go.Mesh3d(
            x=self.mesh_points[:,0], y=self.mesh_points[:,1], z=self.mesh_points[:,2],
            i=self.triangles[:,0], j=self.triangles[:,1], k=self.triangles[:,2],
            **mesh_kwargs
        )

    def plot(self, **mesh_kwargs):
        fig = go.Figure(self.to_Mesh3d(**mesh_kwargs))
        fig.update_scenes(aspectmode='data') # set equal axis aspect ratios
        fig.show()

    def save_geometry(self, to: pathlib.Path | str, compressed=False):
        '''
        `to` is the location to save to. Should use the `.npz` file extension.
        NOTE: does NOT save `self.metadata`.
        '''
        save = np.savez if not compressed else np.savez_compressed
        save(
            to,
            path_points=self.path_points,
            mesh_points=self.mesh_points,
            triangles=self.triangles,
            capped=self.capped,
            sides=self.sides,
            num_cylinders=self.num_cylinders,
        )

    @classmethod
    def geometry_from_file(cls, file: pathlib.Path | str, *args, **kwargs):
        data = np.load(file, *args, **kwargs)
        out = cls.__new__(cls)
        for attribute, value in data.items():
            setattr(out, attribute, value)
        return out


class FlowTubeMesh(TubeMesh):
    ''' A triangle mesh of conical tubes that follow a path of points. '''
    def __init__(
            self,
            path: np.ndarray | Sequence,
            deviation_threshold_degrees: Real = 90,
            widths: Real | np.ndarray | Sequence = 0.2,
            heights: Real | np.ndarray | Sequence | None = None,
            inplace_path: bool = False,
            **kwargs
    ):
        '''
        `path`, `widths`, `heights`, and `inplace_path` are as described in `TubeMesh`.
        `deviation_threshold_degrees` is the minimum angle considered to be "sharp".
        `**kwargs` are passed directly to the `TubeMesh` constructor.
        '''
        # Store initial points internally
        self._path_points = path if inplace_path else self.make_valid_path(path)

        # Find sharp corners
        diffs = np.diff(self._path_points, axis=0)
        diffs /= np.linalg.norm(diffs, axis=1, keepdims=True) # normalise magnitudes
        relative_direction_cosines = np.einsum('ij,ij->i', diffs[1:], diffs[:-1]) # dot-products
        self._sharp_corners = np.empty(len(self._path_points), dtype=bool)
        self._sharp_corners[[0,-1]] = False # the ends aren't corners
        self._sharp_corners[1:-1] = \
            relative_direction_cosines < np.cos(np.deg2rad(deviation_threshold_degrees))
        self._sharp_doubles = np.where(self._sharp_corners)[0]

        # Duplicate relevant corner points (but not the ends)
        path = self._duplicate_sharp_corner_rows(self._path_points)

        widths = np.reshape(widths, (-1,1))
        if widths.size != 1:
            widths = self._duplicate_sharp_corner_rows(widths)

        if heights is not None:
            heights = np.reshape(heights, (-1,1))
            if heights.size != 1:
                heights = self._duplicate_sharp_corner_rows(heights)

        super().__init__(path, widths, heights, inplace_path=True, **kwargs)

    def _duplicate_sharp_corner_rows(self, array: np.ndarray, offset=0):
        # TODO confirm offset behaviour
        doubles = self._sharp_doubles if not offset else self._sharp_doubles - offset
        return np.insert(array, doubles, array[self._sharp_corners[offset:]], axis=0)

    def calculate_corner_tangents(self, path_points):
        # Needs to be a mix of actual tangents (like Tube)
        #  and segment directions (like Chamfered)

        # Tube:
        # [ a,   b,   c,   d,   e,   f,   g, ...,   y,  z]
        # [ab, abc, bcd, cde, def, efg, fgh, ..., xyz, yz]

        # Chamfered:
        # [ a,  b,  b,  c,  c,  d,  d,  e,  e, ...,  y,  y,  z]
        # [ 0,  ?,  1,  ?,  1,  ?,  1,  ?,  1, ...,  ?,  1,  0]
        # [ab, ab, bc, bc, cd, cd, de, de, ef, ..., xy, yz, yz]

        # FlowTube
        # [ a,   b,        c,   d,       e,      f,   g, ...,   y,  z] self._path_points
        # [ a,   b,  c1,  c2,   d,  e1, e2, f1, f2,   g, ...,   y,  z] path_points
        # [ 0,   0,        1,   0,       1,      1,   0, ...,   0,  0] self._sharp_corners
        # Calculate path segment direction vectors
        path_directions = np.empty_like(self._path_points)
        path_directions[:-1] = self._path_points[1:] - self._path_points[:-1]
        # Set the last point to have the same direction as its segment
        path_directions[-1] = path_directions[-2]
        # Normalise directions to avoid tangents being scaled by segment lengths
        path_directions /= np.linalg.norm(path_directions, axis=1, keepdims=True)
        # NOTE: it may be possible to do this step as an insert lower down
        corner_tangents = self._duplicate_sharp_corner_rows(path_directions)
        #>[ab,  bc,  cd,  cd,  de,  ef, ef, fg, fg,  gh, ...,  yz, yz] corner_tangents
        composite_mask = np.insert(np.uint8(self._sharp_corners), self._sharp_doubles, 2)
        composite_mask[[0, -1]] = 3 # set ends to a unique value
        #>[ 3,   0,   2,   1,   0,   2,  1,  2,  1,   0, ...,   0,  3] composite_mask
        segment_ends = np.where(composite_mask == 2)[0]
        corner_tangents[segment_ends] = corner_tangents[segment_ends-1]
        smooth_corners = np.where(composite_mask == 0)[0]
        corner_tangents[smooth_corners] += corner_tangents[smooth_corners-1]
        #>[ab, abc,  bc,  cd, cde,  de, ef, ef, fg, fgh, ..., xyz, yz] corner_tangents
        return corner_tangents

    def to_Mesh3d(
            self,
            colors: np.ndarray | list[Real | str] | str | None = None,
            **mesh_kwargs
    ) -> go.Mesh3d:
        '''
        `colors` should be either
            - `None` (to use self.metadata / plotly's default / configure elsewhere)
            - a single color for all the tubes,
            - N colors denoting the color at each path point (with blends between),
            - N-1 colors denoting the (constant) color of each tube
            - N+1 colors denoting the color of each tube + the endcaps
                -> Only applicable if the mesh was generated with `capped`=True
            Each color can be either
                - A hex string (e.g. '#ff0000')
                - An rgb/rgba string (e.g. 'rgb(255,0,0)'/'rgba(0,255,255,0.3)')
                - An hsl/hsla string (e.g. 'hsl(0,100%,50%)')
                - An hsv/hsva string (e.g. 'hsv(0,100%,100%)')
                - A named CSS color
                - A number that will be interpreted as a color
                 according to mesh3d.colorscale
        '''
        N = len(self._path_points)
        # default to stored metadata (if available)
        if colors is None:
            colors = self.metadata.get('colors')

        # turn high level path colors into low level path colors
        if colors is not None:
            if isinstance(colors, str):
                n = 1
            else:
                n = len(colors)
                # make into a column to allow row insertion
                colors = np.array(colors, dtype=object).reshape((-1, 1))

            if n == N:
                colors = self._duplicate_sharp_corner_rows(colors)
            elif n == N-1:
                colors = self._duplicate_sharp_corner_rows(colors, offset=1)
            elif n == N+1:
                path_colors = colors
                colors = np.empty((len(colors)+len(self._sharp_doubles),1), dtype=object)
                colors[0] = path_colors[0]
                colors[1:] = self._duplicate_sharp_corner_rows(path_colors)

            if not isinstance(colors, str):
                colors = colors.flatten()
        return super().to_Mesh3d(colors, **mesh_kwargs)


class CylindersMesh(TubeMesh):
    ''' A triangle mesh of elliptic cylinder tubes that follow a path,
        with conical/chamfered transitions. '''
    def __init__(
            self,
            path: np.ndarray | Sequence,
            separation: Real | np.ndarray = 0,
            transition_type: str = 'widen',
            widths: Real | np.ndarray | Sequence = 0.2,
            heights: Real | np.ndarray | Sequence | None = None,
            inplace_path: bool = False,
            **kwargs
    ):
        '''
        `path` should contain N points to 'draw' a tube along.
            Points are 3D (x,y,z), but if specified as 2D will assume z=0.
            Successive points are expected to be distinct (i.e. x[i] != x[i+1]).
        `separation` is the tangential separation at each internal point on the path.
            Determines the transition length between tubes of different diameters,
              and the chamfer length for path corners.
            It should be either
                - a single non-negative numerical value that applies to all internal points
                - N-2 non-negative numbers to control each separation individually
        `transition_type` should be one of
            - "widen" to rotate each tube such that a chamfer that's `separation` long
             can pass through the corner, maintaining the corner tangent
            - "cut" (TODO) to cut off corners with a chamfer that's `separation` long
            Only applies if `separation` is non-zero.
        `widths` should be either
            - a single numerical value that applies to all cylinders
            - N-1 numbers denoting the (constant) width of each elliptic cylinder
        `heights` is like `widths`.
            If left as `None`, uses the `widths` value (creating circular cylinders).
        `inplace_path` is a flag specifying that `path` is already a valid numpy
            array of 3D points with float values, and will not be changed externally
            so can safely be used directly (instead of via a copy).
        `**kwargs` are passed directly to the `TubeMesh` constructor.
        '''
        # Store initial points internally
        self._path_points = path if inplace_path else self.make_valid_path(path)
        N = len(self._path_points)

        # Duplicate all internal corners (but not the ends)
        path = self._path_points.repeat(2, axis=0)[1:-1]

        # Handle tube separations (if relevant)
        # TODO: allow `separation`="minimal"
        if np.any(separation != 0):
            scale = np.reshape(separation, (-1,1)) / 2
            # determine offset directions
            if transition_type == 'widen':
                # shift path points back along corner tangent
                offsets = super().calculate_corner_tangents(self._path_points)[1:-1]
                # scale offsets to specified separation lengths
                offsets /= np.linalg.norm(offsets, axis=1, keepdims=True)
                offsets *= scale
                pull_back = push_along = offsets
            elif transition_type == 'cut':
                # shift path points back along segment vectors
                segment_vectors = np.diff(self._path_points, axis=0)
                # scale offsets to specified separation lengths
                segment_vectors /= np.linalg.norm(segment_vectors, axis=1, keepdims=True)
                pull_back = segment_vectors[:-1] * scale
                push_along = segment_vectors[1:] * scale
            else:
                raise ValueError("transition type should be one of 'cut'/'widen'.")

            path[1:-1:2] -= pull_back
            path[2:-1:2] += push_along

        this_class = self.__class__.__name__
        widths = np.reshape(widths, (-1,1))
        if (W := widths.size) != 1:
            assert W == N-1, \
                f'{this_class} requires 1 or {N-1=} widths, not {W}'
            widths = widths.repeat(2, axis=0)

        if heights is not None:
            heights = np.reshape(heights, (-1,1))
            if (H := heights.size) != 1:
                assert H == N-1, \
                    f'{this_class} requires 1 or {N-1=} heights, not {H}'
                heights = heights.repeat(2, axis=0)

        super().__init__(path, widths, heights, inplace_path=True, **kwargs)

    @staticmethod
    def calculate_corner_tangents(path_points):
        # Calculate path segment direction vectors
        corner_tangents = np.empty_like(path_points)
        corner_tangents[:-1] = path_points[1:] - path_points[:-1]
        # Set the cylinder ends to have the same direction as their starts
        corner_tangents[1::2] = corner_tangents[::2]
        return corner_tangents

    def to_Mesh3d(
            self,
            colors: np.ndarray | list[Real | str] | str | None = None,
            corner_colors: np.ndarray | list[Real | str] | str = None,
            **mesh_kwargs
    ) -> go.Mesh3d:
        '''
        `colors` should be either
            - `None` (to use self.metadata / plotly's default / configure elsewhere)
            - a single color for all the tubes,
            - N colors denoting the color at each path point (with blends between),
                -> ignores `corner_colors`
            - N-1 colors denoting the (constant) color of each cylinder
                -> Requires `corner_colors` to be specified
            Each color can be either
                - A hex string (e.g. '#ff0000')
                - An rgb/rgba string (e.g. 'rgb(255,0,0)'/'rgba(0,255,255,0.3)')
                - An hsl/hsla string (e.g. 'hsl(0,100%,50%)')
                - An hsv/hsva string (e.g. 'hsv(0,100%,100%)')
                - A named CSS color
                - A number that will be interpreted as a color
                 according to mesh3d.colorscale
        `corner_colors` should be either
            - a single color for all the corners,
            - N colors denoting the color of the endcaps and corners
            - N-2 colors denoting the color of each corner
            - `None` to get the corner colors from the provided 1 or N `colors`,
             or if `colors` is also `None`
        '''
        N = len(self._path_points)
        # default to stored metadata (if available)
        if colors is None:
            colors = self.metadata.get('colors')
        if corner_colors is None:
            corner_colors = self.metadata.get('corner_colors')

        # turn high level path colors into low level path colors
        if colors is not None:
            n = 1 if isinstance(colors, str) else len(colors)
            if n == N:
                colors = np.repeat(colors, 2)[1:-1]
            elif corner_colors is not None:
                tube_colors = colors
                colors = np.empty(self.num_cylinders+2, dtype=object)
                if self.capped:
                    colors[::2] = corner_colors
                    colors[1:-1:2] = tube_colors
                else:
                    colors[::2] = tube_colors
                    colors[1:-1:2] = corner_colors

        return super().to_Mesh3d(colors, **mesh_kwargs)


if __name__ == '__main__':
    from time import perf_counter

    print('Generating path... ', end=' '*9)
    t_start = perf_counter()
    """
    # long helix path
    t=np.linspace(0,1,100000)
    path = np.empty((len(t),3))
    path[:,2] = t*100
    theta = 2*np.pi*t*1000
    path[:,0] = 7*np.cos(theta)
    path[:,1] = 5*np.sin(theta)
    """
    path = np.array([
        [0,0,0],
        [5,0,0],#1],
        [10,0,2],
        [7,1,1.5],
        [11,1,3],
    ], dtype=float)
    widths = [0.4, 0.8, 0.8, 0.6, 0.8]
    heights = [0.3, 0.6, 0.6, 0.45, 0.6]#0.2#(np.random.rand(len(path))+0.5) / 3
    t_path_gen = perf_counter()
    print(f'DONE [{t_path_gen - t_start:.3f}s]\nGenerating mesh data... ', end=' '*4)

    offsets = []
    offset_proportion = 1 + 0.1 # 10%
    max_dims = [max(dim) for dim in (widths, heights)]
    for axis in range(1,1+2):
        vals = path[:,axis]
        half_dim = max_dims[axis-1] / 2
        min_, max_ = vals.min()-half_dim, vals.max()+half_dim
        ptp = max_ - min_
        offset = np.zeros(3)
        offset[axis] = offset_proportion * ptp
        offsets.append(offset)
    side, up = offsets

    kwargs = dict(sides=8, rounding_strength=0.5, inplace_path=True, capped=True)
    meshes = (
        TubeMesh(path+side, widths=widths, heights=heights, **kwargs),
        TubeMesh(path+side+up, widths=widths, heights=heights, **kwargs),
        FlowTubeMesh(path, widths=widths, heights=heights, **kwargs),
        FlowTubeMesh(path+up, widths=widths, heights=heights, **kwargs),
        CylindersMesh(path-side, widths=widths[:-1], heights=heights[:-1],
                      separation=0.5, transition_type='cut', **kwargs),
        CylindersMesh(path-side+up, widths=widths[:-1], heights=heights[:-1],
                      separation=0.5, **kwargs),
    )
    t_mesh_data = perf_counter()
    print(f'DONE [{t_mesh_data - t_path_gen:.3f}s]\nGenerating plotly meshes... ', end='')

    colors = [
        'cyan',
        'red',
        'red',
        'green',
        'blue',
    ]

    plotly_meshes = (
        meshes[0].to_Mesh3d(colors=colors),
        meshes[1].to_Mesh3d(colors=colors[:-1]),
        meshes[2].to_Mesh3d(colors=colors),
        meshes[3].to_Mesh3d(colors=colors[:-1]),
        meshes[4].to_Mesh3d(colors=colors),
        meshes[5].to_Mesh3d(colors=colors[:-1], corner_colors='yellow'),
    )

    t_plotly_mesh = perf_counter()
    print(f'DONE [{t_plotly_mesh - t_mesh_data:.3f}s]\nCreating plot... ', end=' '*11)

    fig=go.Figure(plotly_meshes)
    fig.update_scenes(aspectmode='data') # set equal axis aspect ratios
    t_fig = perf_counter()
    print(f'DONE [{t_fig - t_plotly_mesh:.3f}s]\nDisplaying figure... ', end=' '*7)

    fig.show()
    t_show = perf_counter()
    print(f'DONE [{t_show - t_fig:.3f}s]\nGenerating example STLs... ', end=' ')

    meshes[2].to_stl('flow_tube_ascii.stl', binary=False)
    meshes[4].to_stl('cylinders_tube_binary.stl')
    multi_exporter = MeshExporter(bodies=meshes[::2])
    multi_exporter.to_stl('three_tubes_ascii.stl', binary=False)
    multi_exporter.to_stl('three_tubes_binary.stl')
    multi_exporter.to_stl('separate_tubes.stl', combined_file=False)


    print(f'DONE [{perf_counter() - t_show:.3f}s]')
