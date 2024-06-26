default_initial_settings = {
    "name": "Skriware 2",
    "manufacturer": "Skriware",
    "start_gcode": "G90 ;absolute positioning\nM82 ;set extruder to absolute mode\nM420 S1 Z0.7 ;enable bed levelling\nG1 Z10 F250 ;move the platform down 10mm\nM107 ;fan off\nM42 P11 S255 ;turn on front fan\nM140 S{data['bed_temp']}\nM104 T0 S{data['nozzle_temp'], 0}\nM104 T1 S{data['nozzle_temp'], 1}\nG1 F2500 Y260 X0\nM190 S{data['bed_temp']}\nM109 T0 S{data['nozzle_temp'], 0}\nM109 T1 S{data['nozzle_temp'], 1}\nM60 ;enable E-FADE Algorithm\nM62 A ;filament sensor off\nG92 E0 ;zero the extruded length\nT1\nG92 E0;zero the extruded length\nG1 F300 Z0.3\nG1 F1200 X20\nG1 F1200 X180 E21 ;extrude 21 mm of feed stock\nG1 F1200 E11\nG1 F300 Z1.5\nG92 E0 ;zero the extruded length again\nT0\nG92 E0 ;zero the extruded length\nG1 F1200 Y258\nG1 F300 Z0.3\nG1 F1200 X40 E21 ;extrude 21 mm of feed stock\nG1 F1200 E11 ;retracting 10 mm\nG1 F300 Z1.5\nM63 A ;filament sensor reset\nM61 A ;filament sensor on\nG92 E0 ;zero the extruded length again\nM58 ;end of Start G-Code and signal retract management\nT{data['extruder_number']}",
    "end_gcode": "M59\nG92 E0\nG1 E-10 F300\nM104 T0 S0\nM104 T1 S0\nM140 S0\nG28 X0 Y0\nM84\nM106 S0\nM107\nM220 S100",
    "bed_temp": 50,
    "nozzle_temp": 200,
    "material_flow_percent": 99,
    "print_speed": 20,
    "travel_speed": 120,
    "dia_feed": 1.75,
    "build_volume_x": 210,
    "build_volume_y": 260,
    "build_volume_z": 210,
}
