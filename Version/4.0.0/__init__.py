# -*- coding: utf-8 -*-

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load qgisfmeformconnector class from file qgisfmeformconnector.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .qgisfmeformconnector import qgisfmeformconnector
    return qgisfmeformconnector(iface)