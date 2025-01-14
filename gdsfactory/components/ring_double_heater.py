from __future__ import annotations

from functools import partial

import gdsfactory as gf
from gdsfactory.component import Component
from gdsfactory.components.bend_euler import bend_euler
from gdsfactory.components.coupler_ring import coupler_ring
from gdsfactory.components.straight import straight
from gdsfactory.components.via_stack import via_stack_heater_m3
from gdsfactory.typings import ComponentFactory, ComponentSpec, CrossSectionSpec, Float2

via_stack_heater_m3_mini = partial(via_stack_heater_m3, size=(4, 4))


@gf.cell
def ring_double_heater(
    gap: float = 0.2,
    radius: float = 10.0,
    length_x: float = 1.0,
    length_y: float = 0.01,
    coupler_ring: ComponentFactory = coupler_ring,
    coupler_ring_top: ComponentFactory | None = None,
    straight: ComponentFactory = straight,
    bend: ComponentFactory = bend_euler,
    cross_section_heater: CrossSectionSpec = "xs_heater_metal",
    cross_section_waveguide_heater: CrossSectionSpec = "xs_sc_heater_metal",
    cross_section: CrossSectionSpec = "xs_sc",
    via_stack: ComponentSpec = via_stack_heater_m3_mini,
    port_orientation: float | None = None,
    via_stack_offset: Float2 = (1, 0),
) -> Component:
    """Returns a double bus ring with heater on top.

    two couplers (ct: top, cb: bottom)
    connected with two vertical straights (sl: left, sr: right)

    Args:
        gap: gap between for coupler.
        radius: for the bend and coupler.
        length_x: ring coupler length.
        length_y: vertical straight length.
        coupler_ring: ring coupler spec.
        coupler_ring_top: ring coupler spec for coupler away from vias (defaults to coupler_ring)
        straight: straight spec.
        bend: bend spec.
        cross_section_heater: for heater.
        cross_section_waveguide_heater: for waveguide with heater.
        cross_section: for regular waveguide.
        via_stack: for heater to routing metal.
        port_orientation: for electrical ports to promote from via_stack.
        via_stack_offset: x,y offset for via_stack.

    .. code::

         --==ct==--
          |      |
          sl     sr length_y
          |      |
         --==cb==-- gap

          length_x
    """
    gap = gf.snap.snap_to_grid(gap, grid_factor=2)

    coupler_ring_top = coupler_ring_top or coupler_ring

    coupler_component = coupler_ring(
        gap=gap,
        radius=radius,
        length_x=length_x,
        bend=bend,
        cross_section=cross_section,
        cross_section_bend=cross_section_waveguide_heater,
    )
    coupler_component_top = gf.get_component(
        coupler_ring_top,
        gap=gap,
        radius=radius,
        length_x=length_x,
        bend=bend,
        cross_section=cross_section,
        cross_section_bend=cross_section_waveguide_heater,
    )
    straight_component = straight(
        length=length_y,
        cross_section=cross_section_waveguide_heater,
    )

    c = Component()
    cb = c.add_ref(coupler_component)
    ct = c.add_ref(coupler_component_top)
    sl = c.add_ref(straight_component)
    sr = c.add_ref(straight_component)

    sl.connect(port="o1", destination=cb.ports["o2"])
    ct.connect(port="o3", destination=sl.ports["o2"])
    sr.connect(port="o2", destination=ct.ports["o2"])
    c.add_port("o1", port=cb.ports["o1"])
    c.add_port("o2", port=cb.ports["o4"])
    c.add_port("o3", port=ct.ports["o4"])
    c.add_port("o4", port=ct.ports["o1"])

    via = gf.get_component(via_stack)
    c1 = c << via
    c2 = c << via
    c1.xmax = -length_x / 2 + cb.x - via_stack_offset[0]
    c2.xmin = +length_x / 2 + cb.x + via_stack_offset[0]
    c1.movey(via_stack_offset[1])
    c2.movey(via_stack_offset[1])

    p1 = c1.get_ports_list(orientation=port_orientation)
    p2 = c2.get_ports_list(orientation=port_orientation)
    valid_orientations = {p.orientation for p in via.ports.values()}

    if not p1:
        raise ValueError(
            f"No ports found for port_orientation {port_orientation} in {valid_orientations}"
        )

    c.add_ports(p1, prefix="l_")
    c.add_ports(p2, prefix="r_")

    heater_top = c << straight(
        length=length_x,
        cross_section=cross_section_heater,
    )
    heater_top.connect("e1", ct["e1"])
    return c


if __name__ == "__main__":
    c = ring_double_heater()
    c.show()
