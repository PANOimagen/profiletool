# test_dist.py is a manual QGIS Python-console scratch snippet (it imports qgis
# and uses `iface`), not an automated test -- skip it during collection so the
# suite runs outside QGIS.
collect_ignore = ["test_dist.py"]
