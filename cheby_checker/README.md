# 2020-08-04
# MJP
# Summary of WIP and To-Do

# To Date / WIP 

- In rough order of usage / data-flow, the following modules should exist ...

### obs_pos.py

- Functionality to allow calculation of observatory positions. 
- It's not at all efficient, but I want to have the function outside of any of the other modules

 ### mpc_nbody & parse_input

 - Wrapper around REBOUND 
 - See notebooks/Demonstate_Functionality_mpc_nbody.ipynb
 
 ### orbit_cheby
 
 - The main work-horse of the package, based around MSC (Multi Sector Cheby) class. 
 - Contains functionalities to fit MSC to nbody data, evaluate MSCs for ephemeris (see below), calculate RA,Dec from Cartesians, etc etc
 - See notebooks/Demonstrate_Orbital_Chebyshev_Functionality.ipynb
 
 ### precalc & sql 
 
 - The precalc routines perform the necessary precalculations (e.g. nightly healpix locations) and then save the data into the sqlite db
 - The sql module handles all of the reads & writes to/from the sqlite db. 
 - notebooks/Demonstrate_SQLandPreCalc.ipynb 
 
 ### ephem
 
 - Very light wrapper around MSC class. Generates an ephemeris (sky-posn, etc) for given object(s).
 - Function(s) sketched-out but not tested / implemented in any way
 
### mpchecker2
 
- Contains stub functions to do *all* checking-related work (pCheck, MPChecker, CheckID, ...)
- Functions sketched-out but not tested / implemented in any way
- A notebook with stub sections in it exists, notebooks/http://localhost:8867/notebooks/Demonstrate_EndToEnd_Orbit_Checking.ipynb, but with little content

### data_classes

- Classes to hold ad-hoc data (detections, pointing, etc) used by various check functions
- Some tests written in tests/towards_tests_of_data_classes.py




# To Do 


 - Test mpc_nbody works in cheby_checker [MA]

- Add functionality from "playing_with_convex_hulls_and_ellipsoid_representations" to allow generation of ellipsoid boundary & calculation of overlap of convex hulls. This should probably be added to MSC (boundary) and Detections/Residuals (overlap). [MJP]

- Develop tests of functionalities in mpchecker. Start with pCheck. [MJP]