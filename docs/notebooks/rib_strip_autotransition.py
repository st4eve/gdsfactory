# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     custom_cell_magics: kql
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.11.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Routing with different CrossSections
#
# When working in a technologies with multiple waveguide cross-sections, it is useful to differentiate intent layers for the different waveguide types
# and assign default transitions between those layers. In this way, you can easily autotransition between the different cross-section types.
#
# ## Setting up your PDK
#
# Let's first set up a sample PDK with the following key features:
#
# 1. Rib and strip cross-sections with differentiated intent layers.
# 2. Default transitions for each individual cross-section type (width tapers), and also a rib-to-strip transition component to switch between them.
# 3. Preferred routing cross-sections defined for the all-angle router.

# %%
from functools import partial

import gdsfactory as gf
from gdsfactory.cross_section import xs_rc, strip, rib
from gdsfactory.generic_tech import get_generic_pdk
from gdsfactory.read import cell_from_yaml_template
from gdsfactory.routing import all_angle
from gdsfactory.typings import CrossSectionSpec

gf.clear_cache()
gf.config.rich_output()
gf.config.enable_off_grid_ports()
gf.CONF.display_type = "klayout"
generic_pdk = get_generic_pdk()

# define our rib and strip waveguide intent layers
RIB_INTENT_LAYER = (2000, 11)
STRIP_INTENT_LAYER = (2001, 11)

generic_pdk.layers.update(
    RIB_INTENT_LAYER=RIB_INTENT_LAYER, STRIP_INTENT_LAYER=STRIP_INTENT_LAYER
)

# create strip and rib cross-sections, with differentiated intent layers
strip_with_intent = partial(
    strip,
    cladding_layers=[
        "STRIP_INTENT_LAYER"
    ],  # keeping WG layer is nice for compatibility
    cladding_offsets=[0],
    gap=2,
)

rib_with_intent = partial(
    rib,
    cladding_layers=["RIB_INTENT_LAYER"],  # keeping WG layer is nice for compatibility
    cladding_offsets=[0],
    gap=5,
)


# create strip->rib transition component
@gf.cell
def strip_to_rib(width1: float = 0.5, width2: float = 0.5) -> gf.Component:
    c = gf.Component()
    taper = c << gf.c.taper_strip_to_ridge(width1=width1, width2=width2)
    c.add_port(
        "o1",
        port=taper.ports["o1"],
        layer="STRIP_INTENT",
        cross_section=strip_with_intent(width=width1),
        width=width1,
    )
    c.add_port(
        "o2",
        port=taper.ports["o2"],
        layer="RIB_INTENT",
        cross_section=rib_with_intent(width=width2),
        width=width2,
    )
    c.absorb(taper)
    c.info.update(taper.info)
    c.add_route_info(cross_section="r2s", length=c.info["length"])
    return c


# also define a rib->strip component for transitioning the other way
@gf.cell
def rib_to_strip(width1: float = 0.5, width2: float = 0.5) -> gf.Component:
    c = gf.Component()
    taper = c << strip_to_rib(width1=width2, width2=width1)
    c.add_port("o1", port=taper.ports["o2"])
    c.add_port("o2", port=taper.ports["o1"])
    c.info.update(taper.info)
    return c


# create single-layer taper components
@gf.cell
def taper_single_cross_section(
    cross_section: CrossSectionSpec = "xs_sc", width1: float = 0.5, width2: float = 1.0
) -> gf.Component:
    cs1 = gf.get_cross_section(cross_section, width=width1)
    cs2 = gf.get_cross_section(cross_section, width=width2)
    length = abs(width1 - width2) * 10
    c = gf.components.taper_cross_section_linear(cs1, cs2, length=length).copy()
    c.info["length"] = length
    return c


taper_strip = partial(taper_single_cross_section, cross_section="xs_sc")
taper_rib = partial(taper_single_cross_section, cross_section="xs_rc")

# make a new PDK with our required layers, cross-sections, and default transitions
multi_wg_pdk = gf.Pdk(
    base_pdk=generic_pdk,
    name="multi_wg_demo",
    layers={
        "RIB_INTENT": RIB_INTENT_LAYER,
        "STRIP_INTENT": STRIP_INTENT_LAYER,
    },
    cross_sections={
        "xs_rc": rib_with_intent,
        "xs_sc": strip_with_intent,
    },
    layer_transitions={
        RIB_INTENT_LAYER: taper_rib,
        STRIP_INTENT_LAYER: taper_strip,
        (RIB_INTENT_LAYER, STRIP_INTENT_LAYER): rib_to_strip,
        (STRIP_INTENT_LAYER, RIB_INTENT_LAYER): strip_to_rib,
    },
    layer_views=generic_pdk.layer_views,
)

# activate our new PDK
multi_wg_pdk.activate()

# set to prefer rib routing when there is enough space
all_angle.LOW_LOSS_CROSS_SECTIONS.insert(0, "xs_rc")

# %% [markdown]
# Let's quickly demonstrate our new cross-sections and transition component.

# %%
# demonstrate rib and strip waveguides in our new PDK
strip_width = 1
rib_width = 0.7

c = gf.Component()
strip_wg = c << gf.c.straight(cross_section="xs_sc")
rib_wg = c << gf.c.straight(cross_section="xs_rc")
taper = c << strip_to_rib(width1=strip_width, width2=rib_width)
taper.connect("o1", strip_wg.ports["o2"])
rib_wg.connect("o1", taper.ports["o2"])
c.plot()

# %% [markdown]
# ## Autotransitioning with the All-Angle Router
#
# Now that our PDK and settings are all configured, we can see how the all-angle router will
# auto-transition for us between different cross sections.
#
# Because we are using the low-loss connector by default, and the highest priority cross section is rib,
# we will see rib routing anywhere there is enough space to transition.

# %%
from pathlib import Path

from IPython.display import Code, display

from gdsfactory.read import cell_from_yaml_template


def show_yaml_pic(filepath):
    gf.clear_cache()
    cell_name = filepath.stem
    return display(
        Code(filename=filepath, language="yaml+jinja"),
        cell_from_yaml_template(filepath, name=cell_name)(),
    )


# load a yaml PIC, and see how it looks with our new technology
sample_dir = Path("yaml_pics")

basic_sample_fn = sample_dir / "aar_indirect.pic.yml"
show_yaml_pic(basic_sample_fn)


# %%
c = gf.read.from_yaml(yaml_str=basic_sample_fn.read_text())
c.plot()

# %% [markdown]
# You can see that since `gap` is defined in our cross-sections, the bundle router also intelligently picks the appropriate bundle spacing for the cross section used.
#
# Notice how the strip waveguide bundles are much more tightly packed than the rib waveguide bundles in the example below.

# %%
basic_sample_fn2 = sample_dir / "aar_bundles03.pic.yml"
show_yaml_pic(basic_sample_fn2)

# %%
f = cell_from_yaml_template(basic_sample_fn2, name="sample_transition")
c = f()
c.plot()

# %%
