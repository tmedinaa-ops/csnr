# SNAP-10A Model Equations

The governing equations for each focus area, written as the build spec. For each block: the equation, what solves it in the chosen stack (OpenMC for transport/criticality, MOOSE or custom Python for thermal/fuel, a thermoelectric model for conversion), and which terms are the tweakable parameters with their source values from the base set.

Two distinctions to keep straight while reading:
- Governing equation: the conservation law a modern solver already implements. You do not reimplement this, you feed it inputs.
- Constitutive relation / closure: the material laws, cross sections, coefficients, and correlations. This is where the original reports' physics lives and where "tweakable within reason" applies.

Notation is standard. Math renders in Obsidian and most markdown viewers.

---

## 1. Shielding

The four original methods (DTK, AIM-6, FMC-N, 14-0) are four ways to solve or approximate one equation: the steady-state neutron transport equation with a fixed fission source. OpenMC solves it by Monte Carlo, the modern equivalent of FMC-N.

### 1.1 Neutron transport equation (fixed source, multigroup)
This is what OpenMC, MCNP, and DTK solve. For energy group $g$:

$$
\boldsymbol{\Omega}\cdot\nabla \psi_g(\mathbf{r},\boldsymbol{\Omega}) + \Sigma_{t,g}(\mathbf{r})\,\psi_g
= \sum_{g'}\int_{4\pi} \Sigma_{s,g'\to g}(\mathbf{r},\boldsymbol{\Omega}'\!\to\!\boldsymbol{\Omega})\,\psi_{g'}(\mathbf{r},\boldsymbol{\Omega}')\,d\boldsymbol{\Omega}' + S_g(\mathbf{r},\boldsymbol{\Omega})
$$

with the source $S_g = \dfrac{\chi_g}{4\pi}\displaystyle\sum_{g'}\nu\Sigma_{f,g'}\phi_{g'}$ for the in-core fission, and the scalar flux $\phi_g=\int_{4\pi}\psi_g\,d\boldsymbol{\Omega}$.

- DTK (discrete ordinates, $S_8$): discretizes $\boldsymbol{\Omega}$ into a quadrature set $\{\boldsymbol{\Omega}_n,w_n\}$ and sweeps along each direction.
- FMC-N (Monte Carlo): samples particle histories from $S_g$ and tallies $\phi_g$. The reports ran 68,000 histories, 35 lethargy groups, 0.0919 to 18 MeV, with source biasing, splitting, and Russian roulette.
- Solver: OpenMC, continuous energy. You give it the geometry, the fission spectrum $\chi$, and the cross sections; it returns $\phi_g(\mathbf{r})$ and the dose tallies.

Tweakable: cross-section library, LiH number densities (from base set), source spectrum bands ($\chi_g$ fractions 0.8051 / 0.1647 / 0.0295 / 0.000685), core power normalization.

### 1.2 Diffusion approximation (AIM-6)
Drops the angular detail by assuming $\psi_g \approx \frac{1}{4\pi}(\phi_g + 3\mathbf{J}_g\!\cdot\!\boldsymbol{\Omega})$, giving for a slab with transverse leakage:

$$
-\frac{d}{dx}\!\left(D_g\frac{d\phi_g}{dx}\right) + \left(\Sigma_{r,g} + D_g B^2\right)\phi_g
= \sum_{g'\neq g}\Sigma_{s,g'\to g}\,\phi_{g'} + S_g,
\qquad D_g=\frac{1}{3\Sigma_{tr,g}}
$$

The buckling term $B^2=(2.405/R)^2$ is exactly the transverse leakage the report applied; the "no $B^2$" case sets $B^2=0$ for comparison with the infinite-medium removal calc. This is the AIM-6 model and is worth coding in Python as a fast cross-check on OpenMC.

Tweakable: $D_g$, $\Sigma_{r,g}$, shield radius $R$ through $B^2$.

### 1.3 Removal theory (14-0), the calibration target
The crudest method and the one the 0.156 cm$^{-1}$ recommendation is about. Fast flux through the shield attenuates as

$$
\phi(x) = \phi_0\,\mathcal{B}(x)\,e^{-\Sigma_R x}
$$

with $\Sigma_R$ the LiH fast-neutron removal cross section and $\mathcal{B}$ a buildup/geometry factor. For a point kernel through a shadow shield,

$$
\phi(\mathbf{r}) = \frac{S}{4\pi r^2}\,e^{-\Sigma_R r}\,\mathcal{B}(\Sigma_R r).
$$

The whole 8768 study is choosing $\Sigma_R$ so this matches the transport and Monte Carlo flux. Validation target: $\Sigma_R = 0.156\ \mathrm{cm^{-1}}$ reproduces the DTK-anisotropic and FMC-N curves, and switching from 0.128 to 0.156 drops the mating-plane flux by about 6x.

Tweakable: $\Sigma_R$ over 0.128 to 0.170 cm$^{-1}$, density scaling $\Sigma_R \propto \rho$.

### 1.4 Dose and fluence
What the design limits are stated in:

$$
\dot{D}(\mathbf{r}) = \int \phi(\mathbf{r},E)\,\mathcal{R}(E)\,dE,
\qquad
\Phi(\mathbf{r}) = \int_0^{\tau}\!\!\int_{E>E_{\min}} \phi(\mathbf{r},E,t)\,dE\,dt
$$

with $\mathcal{R}(E)$ a response/flux-to-dose function. Limits at the 284.3 cm dose plane: gamma $10^7$ r, fast fluence $10^{12}$ nvt (energy cutoff is the unresolved 0.1 vs 1.0 MeV conflict). The Hurst-dosimeter response attenuates 1.45x less than the bare flux.

---

## 2. Reactor kinetics (BOOMER, TRANCORE-10A)

### 2.1 Point kinetics with delayed neutrons
The backbone of both codes:

$$
\frac{dn}{dt} = \frac{\rho(t)-\beta}{\Lambda}\,n(t) + \sum_{i=1}^{6}\lambda_i C_i,
\qquad
\frac{dC_i}{dt} = \frac{\beta_i}{\Lambda}\,n(t) - \lambda_i C_i
$$

$n$ is power (or neutron density), $C_i$ the six delayed-neutron precursor groups, $\Lambda$ the prompt neutron generation time, $\beta=\sum\beta_i$. TRANCORE uses the simplified characteristic time $\ell/\beta \approx 6.25\times10^{-4}$ s for the SNAP 10A/2 system (the report states this as a ratio near 1600 s$^{-1}$ for $\beta/\ell$; presented here as $\ell/\beta$ to avoid the inversion error). The six-group $\beta_i,\lambda_i$ are not legible in the scans; use a standard U-235 thermal set until NAA-SR-9903 or the ORNL benchmark supplies the originals.

Solver: a stiff ODE integrator in Python (the AIREK III and analog references are what TRANCORE validated against, at < 6.5% peak-flux difference). Note the documented limit: this form cannot be trusted near prompt critical.

Tweakable: $\Lambda$, $\beta_i$, $\lambda_i$, external reactivity ramp $\rho_{ext}(t)$.

### 2.2 Reactivity feedback
The coupling that closes the kinetics. Reactivity is the sum of inserted and temperature feedbacks:

$$
\rho(t) = \rho_{ext}(t) + \alpha_F\big(T_F - T_{F,0}\big) + \alpha_{GU}\big(T_{GU}-T_{GU,0}\big) + \alpha_{GL}\big(T_{GL}-T_{GL,0}\big)
$$

$\alpha_F$ is the prompt fuel coefficient, negative and dominant, coming from the U-ZrH hydride. $\alpha_{GU},\alpha_{GL}$ are the upper and lower grid-plate coefficients, each $-0.05$ ¢/°F (NAA-SR-9720 Table 5). The FS-3 ground test measured an overall prompt coefficient of $-0.29\pm0.02$ ¢/°F, which is the cleanest single validation number for this block.

Tweakable: each $\alpha$, and the feedback temperatures, which come from the thermal model below.

---

## 3. Thermal transient (TRANCORE-10A core temperatures)

### 3.1 Fuel element conduction
Transient heat conduction with the volumetric source set by the kinetics power:

$$
\rho c_p\frac{\partial T}{\partial t} = \frac{1}{r}\frac{\partial}{\partial r}\!\left(k\,r\,\frac{\partial T}{\partial r}\right) + q'''(\mathbf{r},t)
$$

with $q'''$ proportional to $n(t)$ from Section 2 and the spatial power shape (peaking factor 1.98 from the coupled model). Solver: MOOSE heat conduction, or a 1D radial finite-difference in Python.

### 3.2 Coolant energy balance
NaK carrying heat out of the core:

$$
A\,\rho_c c_{p,c}\frac{\partial T_c}{\partial t} + \dot{m}\,c_{p,c}\frac{\partial T_c}{\partial z} = h\,P_h\,(T_{w}-T_c)
$$

with Newton cooling $q'' = h(T_w - T_c)$ at the clad surface. NaK properties and $\dot m = 0.6199$ kg/s from the base set. The thermoelectric-pump thermal sub-model agreed with the 48-node TAP-2 model within 1%.

Validation: peak power, peak outlet temperature, and peak flow within 7.5% of the analog startup model; coupled steady-state fuel temperature 805.6 K average, 853.3 K max.

Tweakable: $k(T)$, $h$, $c_p$, $\dot m$, inlet temperature.

---

## 4. Fuel hydrogen behavior (FUSAK, BOOMER Appendix D)

This is the physics that makes U-ZrH special and is the hardest area to source. FUSAK itself was not retrievable; the equation forms below are from BOOMER Appendix D.

### 4.1 Hydrogen thermomigration (Fick plus Soret)
Hydrogen redistributes under both concentration and temperature gradients:

$$
J = -D\left(\frac{\partial C}{\partial x} + \frac{C\,Q^{*}}{R\,T^{2}}\,\frac{\partial T}{\partial x}\right)
$$

$Q^{*}=1270$ cal/mole is the heat of transport (BOOMER App D), $R=1.987$ cal/mol·K. Setting $J=0$ gives the equilibrium redistribution, hydrogen accumulating in the colder regions. This is the term behind the samarium-oxide diffusion barrier on the fuel.

### 4.2 Hydrogen diffusion coefficient
Arrhenius, with the BOOMER/BMI value:

$$
D(T) = D_0\,e^{-Q/RT}, \qquad D = 0.4\,e^{-10450/T}\ \ \mathrm{(cm^2/s,\ T\ in\ K)}
$$

A modified form matched to AI tests is "power-limited" at a switchover temperature $T_{CH}\approx 2000$ °F, with fuel melting taken at 1925 K.

### 4.3 Equilibrium dissociation pressure
The hydrogen plateau pressure over ZrH$_x$ sets cladding load and permeation. General thermodynamic (van't Hoff) form at fixed composition:

$$
\ln P_{H_2} = A(x) - \frac{\Delta H_{diss}}{R\,T}
$$

with dissociation energy $\Delta H_{diss}=39.6$ kcal/mole (BOOMER App D). The full composition dependence $A(x)$ is the FUSAK-specific closure and is not in hand; flag this as the one fuel relation needing the original report.

### 4.4 Permeation through cladding (Sieverts)
Atomic hydrogen dissolves in proportion to $\sqrt{P}$, so the permeation flux through clad of thickness $d$ is

$$
J_{perm} = \frac{K_p}{d}\left(\sqrt{P_{1}} - \sqrt{P_{2}}\right)
$$

Tweakable across this section: $D_0$, $Q$, $Q^{*}$, $\Delta H_{diss}$, $K_p$, and the H/Zr ratio (still unsourced).

### 4.5 Excursion energy limit (BOOMER coupling)
The safety-relevant output: an uncontrolled excursion below $1 supercritical is terminated by prompt and grid feedback; above $1, hydrogen evolution disassembles the core. The core-melt energy limit is about 160 MW-sec, with hydrogen loss capping energy below that. Disassembly reactivity loss rate is far faster than the hydrogen-loss rate.

---

## 5. Energy conversion (thermoelectric)

NAA-SR-11955 was retrieved June 2026 (full text, UNT Digital Library). Its design-and-analysis equations (Eqs 1-9, printed pp.15-19) match the canonical closure below: open-circuit voltage, converter resistance, load and element currents, terminal voltage, power, and a hot-junction heat balance with exactly four terms (conduction, Peltier, Joule, Thomson). The report explicitly drops Thomson by folding it into a mean Seebeck coefficient over the hot-to-cold range. So this is AI's closure, not just a textbook stand-in. Material is confirmed SiGe, 67 at% Si / 33 at% Ge used (70/30 nominal), tungsten hot shoes, As-doped N legs.

### 5.1 Coupled charge and heat transport
$$
\mathbf{J} = \sigma\big(\mathbf{E} - \alpha\nabla T\big),
\qquad
\mathbf{q} = \alpha T\,\mathbf{J} - k\nabla T
$$

with energy conservation $\nabla\!\cdot\!\mathbf{q} = \mathbf{J}\!\cdot\!\mathbf{E}$ giving the steady heat equation with Joule and Thomson terms:

$$
\nabla\!\cdot\!(k\nabla T) + \frac{J^2}{\sigma} - T\frac{d\alpha}{dT}\,\mathbf{J}\!\cdot\!\nabla T = 0
$$

$\alpha$ Seebeck coefficient, $\sigma$ electrical conductivity, $k$ thermal conductivity, all temperature dependent for SiGe.

### 5.2 Module junction balances and output
For a couple between hot and cold junctions:

$$
Q_h = \alpha I T_h - \tfrac{1}{2}I^2 R + K_{th}(T_h - T_c),
\qquad
Q_c = \alpha I T_c + \tfrac{1}{2}I^2 R + K_{th}(T_h - T_c)
$$

Electrical power and efficiency:

$$
P = Q_h - Q_c = \alpha I (T_h - T_c) - I^2 R,
\qquad
\eta = \frac{P}{Q_h}
$$

### 5.2a Converter-level form (NAA-SR-11955, primary)
The report's discrete equations, for $N$ couples in $n$ parallel paths, couple Seebeck sum $S = S_N + S_P$, resistance per couple $R_0$, conductance per couple $K$:

$$
E_{oc} = \frac{N}{n} S (T_{HJ}-T_{CJ}),
\qquad
R = \frac{N R_0}{n^2},
\qquad
I = \frac{E_{oc}}{(M+1)R},
\qquad
E = \frac{M}{M+1} E_{oc}
$$

with load ratio $M = R_L/R$, element current $i = I/n$, matched-load power $P_m = \dfrac{N S^2 (T_{HJ}-T_{CJ})^2}{4R_0}$, and hot-junction heat input

$$
Q_a = N K (T_{HJ}-T_{CJ}) + N i S\,T_{HJ} - \tfrac{1}{2} N i^2 R_0 .
$$

Design point fixes $N=1440$, $n=2$. Back-solving Table 2 gives the effective constants $S \approx 479\ \mu\text{V/K}$, $R_0 \approx 3.9\ \text{m}\Omega$/couple, $K \approx 0.113\ \text{W/K}$/couple. The Seebeck uses the loaded open-circuit voltage $E_{oc}=V+IR=28.5+20.4(1.40)=57$ V, not the 61.7 V open-circuit reading in Table 2, which belongs to the wider open-circuit $\Delta T$. Pairing 61.7 V with the loaded $\Delta T$ gives 518 $\mu$V/K and makes circuit power and heat-balance power disagree by ~16% (581 vs 676 W); 479 $\mu$V/K is self-consistent. See energy_conversion/Energy_Conversion_Model_Notes.md.

### 5.3 Figure of merit and ceiling efficiency
$$
Z = \frac{\alpha^2 \sigma}{k},
\qquad
\eta_{max} = \left(1-\frac{T_c}{T_h}\right)\frac{\sqrt{1+Z\bar{T}}-1}{\sqrt{1+Z\bar{T}}+\dfrac{T_c}{T_h}}
$$

Validation anchor is now the full NAA-SR-11955 Table 2 design point (primary): 581 We initial at 28.5 V and 20.4 A, heat input 31.90 kWt, overall efficiency 1.82%, device 7.65%, Carnot 23.8%. Average hot junction 902 degF (757 K), average cold junction 604 degF (591 K); the stated 23.8% Carnot uses average NaK (935 degF, 775 K) over average radiator (603 degF, 590 K). Reproduce Table 2 first with the effective lumped constants from 5.2a, then switch to temperature-dependent SiGe curves. Source for those curves is not NAA-SR-Memo-6670 (that memo, retrieved June 2026, is a PbTe apparatus and method memo, wrong material); it is the RCA "Development of Thermoelectric Modules for SNAP 10A" report series (1962-63) and AI module memos NAA-SR-MEMO-10126 and NAA-SR-11205, per 11955's reference list, or the canonical RCA Ge-Si property literature (Dismukes et al. 1964). 11955 Figures 43-50 also plot the SiGe couple performance vs temperature. Flight anchors: ~590 to 600 We peak, ~530 We stabilized, 500 We end-of-life minimum.

Tweakable: $\alpha(T),\sigma(T),k(T)$ for SiGe, $T_h$, $T_c$, load resistance, couple count.

### 5.4 Liquid-metal EM pump (NaK loop)
DC conduction pump developed pressure from the Lorentz force $\mathbf{F}=\mathbf{J}\times\mathbf{B}$:

$$
\Delta p = \frac{B\,I}{w}
$$

for current $I$ across duct width $w$ in field $B$. Pump flow and input power were not found; placeholder until OSTI 4516323 is retrieved.

---

## 6. Coupling and the whole system

### 6.1 Multiphysics coupling (Cardinal)
The areas above couple through temperature feedback. The fixed-point (Picard) loop:

1. OpenMC solves transport at current temperatures, returns power density $q'''(\mathbf{r})$ and $k_{eff}$.
2. MOOSE solves conduction and the fluid energy balance, returns $T(\mathbf{r})$.
3. Temperatures update cross sections (Doppler broadening, density/expansion), feeding back into step 1.
4. Repeat until $k_{eff}$ and $T$ converge.

Validation: coupled $k_{eff}=1.00086\pm0.00024$, fuel and fluid temperatures within ~3 K of NAA-SR-9903.

### 6.2 Total System Simulation (NAA-SR-MEMO-6721)
The whole power unit is a coupled ODE set: point kinetics (Section 2) plus lumped thermal nodes (Section 3) plus the converter (Section 5) plus a control loop driving the reflector drums on a measured temperature or power error. The report was not located; this is the structural form, not its exact constants.

---

## Where the originals end and standard physics begins
- Sections 1.1 to 1.4, 2.1, 3.1, 3.2, 6.1 are standard conservation laws your solvers already implement. You supply inputs.
- Sections 1.3 (the $\Sigma_R$ calibration), 2.2 (the temperature coefficients), 4.1 to 4.4 (hydrogen closures), and 5 (SiGe properties) are the constitutive relations carrying the original physics and your tweakable parameters.
- Unsourced closures to chase before trusting: the FUSAK dissociation-pressure composition term $A(x)$, the original six-group kinetics data, and the SiGe property curves and junction temperatures.
