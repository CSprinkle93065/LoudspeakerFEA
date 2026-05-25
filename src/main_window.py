"""Main application window for LoudspeakerFEA.

PyQt6 GUI — this is the only module that imports PyQt6 widgets.
Follows the LoudspeakerDesigner pattern:
  - Left panel: fixed-width scrollable QScrollArea with stacked QGroupBox widgets
  - Right panel: QTabWidget with matplotlib plots and image display
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import matplotlib
matplotlib.use("qtagg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from src.api import (
    LoudspeakerDesign,
    create_design,
    export_blx_csv,
    export_results_json,
    export_side_leakage_csv,
    get_default_values,
    init_database,
    recalculate_derived,
    run_elmer_simulation,
    save_design,
    load_design,
    list_designs,
    delete_design,
    set_elmer_executable_path,
    set_working_directory,
    update_design_parameter,
)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("LoudspeakerFEA v0.1.3")
        self.setMinimumSize(1280, 800)

        self._design = create_design(name="Design1")
        self._design = recalculate_derived(self._design)

        self._build_menu()
        self._build_central_widget()
        self._build_status_bar()

        try:
            init_database()
        except Exception as e:
            self.statusBar().showMessage(f"DB init warning: {e}")

        self._refresh_all_outputs()

    # ─── Menu ────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("File")

        new_action = file_menu.addAction("New Design")
        new_action.triggered.connect(self._on_new_design)

        save_action = file_menu.addAction("Save Design")
        save_action.triggered.connect(self._on_save_design)

        open_action = file_menu.addAction("Open Design")
        open_action.triggered.connect(self._on_open_design)

        delete_action = file_menu.addAction("Delete Design")
        delete_action.triggered.connect(self._on_delete_design)

        export_menu = file_menu.addMenu("Export")
        export_blx = export_menu.addAction("BL(x) CSV")
        export_blx.triggered.connect(self._on_export_blx)
        export_leak = export_menu.addAction("Side Leakage CSV")
        export_leak.triggered.connect(self._on_export_leakage)
        export_json = export_menu.addAction("Results Summary")
        export_json.triggered.connect(self._on_export_json)

        setup_menu = menu.addMenu("Setup")

        elmer_path_action = setup_menu.addAction("Elmer executable path...")
        elmer_path_action.triggered.connect(self._on_browse_elmer)

        work_dir_action = setup_menu.addAction("Working directory...")
        work_dir_action.triggered.connect(self._on_set_working_directory)

        mesh_size_action = setup_menu.addAction("Mesh size factor...")
        mesh_size_action.triggered.connect(self._on_set_mesh_size_factor)

        show_proc_action = setup_menu.addAction("Show processor...")
        show_proc_action.triggered.connect(self._on_set_show_processor)

        help_menu = menu.addMenu("Help")
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self._on_about)

    # ─── Central Widget ──────────────────────────────────────────────────────

    def _build_central_widget(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel
        left = self._build_left_panel()
        left.setMinimumWidth(420)
        left.setMaximumWidth(520)
        splitter.addWidget(left)

        # Right panel
        right = self._build_right_panel()
        splitter.addWidget(right)
        splitter.setSizes([460, 820])

        self.setCentralWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(8)

        # Group A: Voice Coil
        group_a = QGroupBox("Voice Coil")
        form_a = QFormLayout(group_a)
        self._inp_wire_dia = self._make_spinbox(0.01, 2.0, self._design.wire_diameter, 3)
        self._inp_wire_dia.valueChanged.connect(lambda v: self._update_input("wire_diameter", v))
        form_a.addRow("Wire Diameter (mm)", self._inp_wire_dia)
        self._inp_vc_dcr = self._make_spinbox(0.0, 50.0, self._design.vc_wire_dcr, 3)
        self._inp_vc_dcr.valueChanged.connect(lambda v: self._update_input("vc_wire_dcr", v))
        form_a.addRow("VC Wire DCR (Ω)", self._inp_vc_dcr)
        self._inp_tinsel_dcr = self._make_spinbox(0.0, 1.0, self._design.tinsel_wire_dcr, 3)
        self._inp_tinsel_dcr.valueChanged.connect(lambda v: self._update_input("tinsel_wire_dcr", v))
        form_a.addRow("Tinsel Wire DCR (Ω)", self._inp_tinsel_dcr)
        self._inp_coil_id = self._make_spinbox(1.0, 500.0, self._design.coil_id, 2)
        self._inp_coil_id.valueChanged.connect(lambda v: self._update_input("coil_id", v))
        form_a.addRow("Coil I.D. (mm)", self._inp_coil_id)
        self._inp_coil_tol = self._make_spinbox(0.0, 1.0, self._design.coil_id_tolerance, 3)
        self._inp_coil_tol.valueChanged.connect(lambda v: self._update_input("coil_id_tolerance", v))
        form_a.addRow("Coil I.D. Tolerance (mm)", self._inp_coil_tol)
        self._inp_former_thick = self._make_spinbox(0.0, 2.0, self._design.former_thickness, 3)
        self._inp_former_thick.valueChanged.connect(lambda v: self._update_input("former_thickness", v))
        form_a.addRow("Former Thickness (mm)", self._inp_former_thick)
        self._inp_former_len = self._make_spinbox(1.0, 200.0, self._design.former_length, 2)
        self._inp_former_len.valueChanged.connect(lambda v: self._update_input("former_length", v))
        form_a.addRow("Former Length (mm)", self._inp_former_len)
        self._inp_num_layers = self._make_spinbox(1.0, 10.0, self._design.number_of_layers, 1)
        self._inp_num_layers.valueChanged.connect(lambda v: self._update_input("number_of_layers", v))
        form_a.addRow("Number of layers", self._inp_num_layers)
        self._inp_wire_type = QComboBox()
        self._inp_wire_type.addItems(["1 Copper", "2 CCA"])
        self._inp_wire_type.setCurrentIndex(self._design.wire_type - 1)
        self._inp_wire_type.currentIndexChanged.connect(lambda i: self._update_input("wire_type", i + 1))
        form_a.addRow("Wire Type", self._inp_wire_type)
        self._inp_former_type = QComboBox()
        self._inp_former_type.addItems(["1 Kapton", "2 Aluminum", "3 Nomex", "4 Kraft"])
        self._inp_former_type.setCurrentIndex(self._design.former_type - 1)
        self._inp_former_type.currentIndexChanged.connect(lambda i: self._update_input("former_type", i + 1))
        form_a.addRow("Former", self._inp_former_type)
        self._inp_overhang = self._make_spinbox(0.0, 100.0, self._design.overhang, 2)
        self._inp_overhang.valueChanged.connect(lambda v: self._update_input("overhang", v))
        form_a.addRow("Overhang (mm)", self._inp_overhang)

        self._out_total_vc_dcr = QLabel("0.0")
        form_a.addRow("Total VC DCR (Ω)", self._out_total_vc_dcr)
        self._out_len_wire = QLabel("0.0")
        form_a.addRow("Length of Wire (m)", self._out_len_wire)
        self._out_num_turns = QLabel("0.0")
        form_a.addRow("Number of Turns", self._out_num_turns)
        self._out_coil_max_od = QLabel("0.0")
        form_a.addRow("Coil Winding MAX O.D. (mm)", self._out_coil_max_od)
        self._out_ww = QLabel("0.0")
        form_a.addRow("Winding Width (mm)", self._out_ww)
        self._out_mass_former = QLabel("0.0")
        form_a.addRow("Mass of Former (g)", self._out_mass_former)
        self._out_mass_wire = QLabel("0.0")
        form_a.addRow("Mass of wire (g)", self._out_mass_wire)
        self._out_mass_vc = QLabel("0.0")
        form_a.addRow("Mass of Voice Coil (g)", self._out_mass_vc)
        self._out_wire_dia_insul = QLabel("0.0")
        form_a.addRow("Wire Diameter (with insulation) (mm)", self._out_wire_dia_insul)
        self._out_resistivity = QLabel("0.0")
        form_a.addRow("Resistivity ohms per meter", self._out_resistivity)
        self._out_len_per_turn = QLabel("0.0")
        form_a.addRow("Length of Wire per Turn (mm)", self._out_len_per_turn)
        layout.addWidget(group_a)

        # Group B: Motor Geometry
        group_b = QGroupBox("Motor Geometry")
        form_b = QFormLayout(group_b)
        self._inp_magnet_mat = QComboBox()
        self._inp_magnet_mat.addItems([
            "Ceramic5", "NdFe38", "NdFe48", "NdFe35",
            "NdFe38 High Temp", "NdFe39 Super High Temp", "NdFe38 Ultra High Temp"
        ])
        self._inp_magnet_mat.setCurrentText(self._design.magnet_material)
        self._inp_magnet_mat.currentTextChanged.connect(lambda t: self._update_input("magnet_material", t))
        form_b.addRow("Magnet material", self._inp_magnet_mat)
        self._inp_inside_gap = self._make_spinbox(0.0, 10.0, self._design.inside_gap, 2)
        self._inp_inside_gap.valueChanged.connect(lambda v: self._update_input("inside_gap", v))
        form_b.addRow("Inside gap (mm)", self._inp_inside_gap)
        self._inp_outside_gap = self._make_spinbox(0.0, 10.0, self._design.outside_gap, 2)
        self._inp_outside_gap.valueChanged.connect(lambda v: self._update_input("outside_gap", v))
        form_b.addRow("Outside gap (mm)", self._inp_outside_gap)
        self._inp_tp_id = self._make_spinbox(0.0, 500.0, self._design.top_plate_id, 3)
        self._inp_tp_id.valueChanged.connect(lambda v: self._update_input("top_plate_id", v))
        form_b.addRow("Top Plate ID (mm)", self._inp_tp_id)
        self._inp_tp_od = self._make_spinbox(0.0, 500.0, self._design.top_plate_od, 2)
        self._inp_tp_od.valueChanged.connect(lambda v: self._update_input("top_plate_od", v))
        form_b.addRow("Top Plate OD (mm)", self._inp_tp_od)
        self._inp_tp_thick = self._make_spinbox(0.0, 100.0, self._design.top_plate_thickness, 2)
        self._inp_tp_thick.valueChanged.connect(lambda v: self._update_input("top_plate_thickness", v))
        form_b.addRow("Top Plate thickness (mm)", self._inp_tp_thick)
        self._inp_mag_id = self._make_spinbox(0.0, 500.0, self._design.magnet_id, 2)
        self._inp_mag_id.valueChanged.connect(lambda v: self._update_input("magnet_id", v))
        form_b.addRow("Magnet ID (mm)", self._inp_mag_id)
        self._inp_mag_od = self._make_spinbox(0.0, 500.0, self._design.magnet_od, 2)
        self._inp_mag_od.valueChanged.connect(lambda v: self._update_input("magnet_od", v))
        form_b.addRow("Magnet OD (mm)", self._inp_mag_od)
        self._inp_mag_thick = self._make_spinbox(0.0, 200.0, self._design.magnet_thickness, 2)
        self._inp_mag_thick.valueChanged.connect(lambda v: self._update_input("magnet_thickness", v))
        form_b.addRow("Magnet thickness (mm)", self._inp_mag_thick)
        self._inp_pole_od = self._make_spinbox(0.0, 500.0, self._design.pole_od, 2)
        self._inp_pole_od.valueChanged.connect(lambda v: self._update_input("pole_od", v))
        form_b.addRow("Pole OD (mm)", self._inp_pole_od)
        self._inp_pole_vent = self._make_spinbox(0.0, 200.0, self._design.pole_vent_hole, 2)
        self._inp_pole_vent.valueChanged.connect(lambda v: self._update_input("pole_vent_hole", v))
        form_b.addRow("Pole vent hole (mm)", self._inp_pole_vent)
        self._inp_pole_overhang = self._make_spinbox(0.0, 100.0, self._design.pole_overhang, 2)
        self._inp_pole_overhang.valueChanged.connect(lambda v: self._update_input("pole_overhang", v))
        form_b.addRow("Pole overhang (mm)", self._inp_pole_overhang)
        self._inp_bp_od = self._make_spinbox(0.0, 500.0, self._design.bp_od, 2)
        self._inp_bp_od.valueChanged.connect(lambda v: self._update_input("bp_od", v))
        form_b.addRow("BP OD (mm)", self._inp_bp_od)
        self._inp_bp_thick = self._make_spinbox(0.0, 100.0, self._design.bp_thickness, 2)
        self._inp_bp_thick.valueChanged.connect(lambda v: self._update_input("bp_thickness", v))
        form_b.addRow("BP thickness (mm)", self._inp_bp_thick)
        # Bucking magnet inputs removed from UI per requirements
        self._inp_vc_offset = self._make_spinbox(-50.0, 50.0, self._design.vc_offset, 2)
        self._inp_vc_offset.valueChanged.connect(lambda v: self._update_input("vc_offset", v))
        form_b.addRow("VC offset (mm)", self._inp_vc_offset)
        self._inp_leak_dist = self._make_spinbox(0.0, 500.0, self._design.side_leakage_distance, 2)
        self._inp_leak_dist.valueChanged.connect(lambda v: self._update_input("side_leakage_distance", v))
        form_b.addRow("Side Leakage Measurement Distance (mm)", self._inp_leak_dist)
        self._out_pole_height = QLabel("0.0")
        form_b.addRow("Pole Height (mm)", self._out_pole_height)
        self._out_vc_loc_dia = QLabel("0.0")
        form_b.addRow("VC location Diameter (mm)", self._out_vc_loc_dia)
        self._out_mech_xmax = QLabel("0.0")
        form_b.addRow("Mechanical Xmax (mm)", self._out_mech_xmax)
        layout.addWidget(group_b)

        # Group C: FEA
        group_c = QGroupBox("FEA")
        form_c = QFormLayout(group_c)
        calc_btn = QPushButton("Calculate B (Run Elmer)")
        calc_btn.clicked.connect(self._on_run_elmer)
        form_c.addRow(calc_btn)
        self._out_fea_b = QLabel("0.0")
        form_c.addRow("FEA B (T)", self._out_fea_b)
        self._out_bl = QLabel("0.0")
        form_c.addRow("BL (T·m)", self._out_bl)
        self._inp_bl_threshold = self._make_spinbox(0.0, 1.0, self._design.bl_threshold_pct, 3)
        self._inp_bl_threshold.valueChanged.connect(lambda v: self._update_input("bl_threshold_pct", v))
        form_c.addRow("BL/BLmax (%)", self._inp_bl_threshold)
        self._out_xmax_82bl = QLabel("0.0")
        form_c.addRow("Xmax @ 82%BL (mm)", self._out_xmax_82bl)
        self._out_bl_at_thresh = QLabel("0.0")
        form_c.addRow("Bl @ 82%BLmax (T·m)", self._out_bl_at_thresh)
        self._out_max_leak = QLabel("0.0")
        form_c.addRow("Max Side Leakage @ 100mm", self._out_max_leak)
        self._out_prim_mag_b = QLabel("0.0")
        form_c.addRow("Primary Magnet average B", self._out_prim_mag_b)
        self._out_sec_mag_b = QLabel("N/A")
        form_c.addRow("Secondary Magnet average B", self._out_sec_mag_b)
        layout.addWidget(group_c)

        layout.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _build_right_panel(self) -> QWidget:
        tabs = QTabWidget()

        # Tab 1: BL(x) Curve
        self._fig_blx = Figure(figsize=(8, 5), dpi=100)
        self._canvas_blx = FigureCanvasQTAgg(self._fig_blx)
        self._ax_blx = self._fig_blx.add_subplot(111)
        self._ax_blx.set_xlabel("Displacement (mm)")
        self._ax_blx.set_ylabel("BL (T·m)")
        self._ax_blx.set_title("BL(x) Curve")
        tabs.addTab(self._canvas_blx, "BL(x) Curve")

        # Tab 2: Side Leakage
        self._fig_leak = Figure(figsize=(8, 5), dpi=100)
        self._canvas_leak = FigureCanvasQTAgg(self._fig_leak)
        self._ax_leak = self._fig_leak.add_subplot(111)
        self._ax_leak.set_xlabel("Index")
        self._ax_leak.set_ylabel("Leakage (G)")
        self._ax_leak.set_title("Side Leakage")
        tabs.addTab(self._canvas_leak, "Side Leakage")

        # Tab 3: FEA Geometry
        self._fea_image_label = QLabel("Run Elmer simulation to display geometry image.")
        self._fea_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tabs.addTab(self._fea_image_label, "FEA Geometry")

        return tabs

    def _build_status_bar(self):
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _make_spinbox(self, min_val: float, max_val: float, value: float, decimals: int) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(min_val, max_val)
        sb.setDecimals(decimals)
        sb.setValue(value)
        sb.setKeyboardTracking(False)
        return sb

    def _update_input(self, field_name: str, value: Any):
        self._design = update_design_parameter(self._design, field_name, value)
        self._refresh_all_outputs()

    def _refresh_all_outputs(self):
        d = self._design
        self._out_total_vc_dcr.setText(f"{d.total_vc_dcr:.4f}")
        self._out_len_wire.setText(f"{d.length_of_wire:.4f}")
        self._out_num_turns.setText(f"{d.number_of_turns:.4f}")
        self._out_coil_max_od.setText(f"{d.coil_winding_max_od:.4f}")
        self._out_ww.setText(f"{d.ww:.2f}")
        self._out_mass_former.setText(f"{d.mass_of_former:.4f}")
        self._out_mass_wire.setText(f"{d.mass_of_wire:.4f}")
        self._out_mass_vc.setText(f"{d.mass_of_voice_coil:.4f}")
        self._out_wire_dia_insul.setText(f"{d.wire_dia_with_insulation:.4f}")
        self._out_resistivity.setText(f"{d.resistivity_ohms_per_m:.6f}")
        self._out_len_per_turn.setText(f"{d.length_of_wire_per_turn:.4f}")
        self._out_pole_height.setText(f"{d.pole_height:.2f}")
        self._out_vc_loc_dia.setText(f"{d.vc_location_diameter:.2f}")
        self._out_mech_xmax.setText(f"{d.mechanical_xmax:.1f}")
        self._out_fea_b.setText(f"{d.fea_b:.6f}")
        self._out_bl.setText(f"{d.bl:.2f}")
        self._out_xmax_82bl.setText(f"{d.xmax_at_82bl:.2f}")
        self._out_bl_at_thresh.setText(f"{d.bl_at_threshold:.4f}")
        self._out_max_leak.setText(f"{d.max_side_leakage:.6f}")
        self._out_prim_mag_b.setText(f"{d.primary_magnet_avg_b:.6f}")
        self._out_sec_mag_b.setText("N/A")

        # Refresh plots
        self._refresh_blx_plot()
        self._refresh_leakage_plot()

        # Load FEA geometry image
        png_path = Path(d.working_directory) / "B-Field.png"
        if png_path.exists():
            pixmap = QPixmap(str(png_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._fea_image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._fea_image_label.setPixmap(scaled)
                self._fea_image_label.setText("")
            else:
                self._fea_image_label.setText("Failed to load B-Field.png")
                self._fea_image_label.setPixmap(QPixmap())
        else:
            self._fea_image_label.setText("Run Elmer simulation to display geometry image.")
            self._fea_image_label.setPixmap(QPixmap())

    def _refresh_blx_plot(self):
        self._ax_blx.clear()
        if self._design.bl_x_data:
            xs = [x for x, _ in self._design.bl_x_data]
            ys = [bl for _, bl in self._design.bl_x_data]
            self._ax_blx.plot(xs, ys, marker="o", linestyle="-")
        self._ax_blx.set_xlabel("Displacement (mm)")
        self._ax_blx.set_ylabel("BL (T·m)")
        self._ax_blx.set_title("BL(x) Curve")
        self._ax_blx.set_ylim(bottom=0)
        self._fig_blx.tight_layout()
        self._canvas_blx.draw()

    def _refresh_leakage_plot(self):
        self._ax_leak.clear()
        if self._design.side_leakage_data:
            self._ax_leak.plot(self._design.side_leakage_data, marker="", linestyle="-")
        self._ax_leak.set_xlabel("Index")
        self._ax_leak.set_ylabel("Leakage (G)")
        self._ax_leak.set_title("Side Leakage")
        self._fig_leak.tight_layout()
        self._canvas_leak.draw()

    # ─── Actions ─────────────────────────────────────────────────────────────

    def _on_new_design(self):
        self._design = create_design(name="Design1")
        self._design = recalculate_derived(self._design)
        self._sync_inputs_from_design()
        self._refresh_all_outputs()
        self.statusBar().showMessage("New design created")

    def _on_save_design(self):
        try:
            design_id = save_design(self._design)
            self.statusBar().showMessage(f"Design saved (ID {design_id})")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _on_open_design(self):
        designs = list_designs()
        if not designs:
            QMessageBox.information(self, "Open Design", "No saved designs found.")
            return
        items = [f"{d['id']}: {d['name']}" for d in designs]
        from PyQt6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getItem(self, "Open Design", "Select design:", items, 0, False)
        if ok and text:
            design_id = int(text.split(":")[0])
            try:
                self._design = load_design(design_id)
                self._sync_inputs_from_design()
                self._refresh_all_outputs()
                self.statusBar().showMessage(f"Loaded design {design_id}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", str(e))

    def _on_delete_design(self):
        designs = list_designs()
        if not designs:
            QMessageBox.information(self, "Delete Design", "No saved designs found.")
            return
        items = [f"{d['id']}: {d['name']}" for d in designs]
        from PyQt6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getItem(self, "Delete Design", "Select design:", items, 0, False)
        if ok and text:
            design_id = int(text.split(":")[0])
            try:
                delete_design(design_id)
                self.statusBar().showMessage(f"Deleted design {design_id}")
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", str(e))

    def _on_export_blx(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export BL(x) CSV", "", "CSV Files (*.csv)")
        if path:
            try:
                export_blx_csv(self._design, path)
                self.statusBar().showMessage(f"Exported BL(x) to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _on_export_leakage(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Side Leakage CSV", "", "CSV Files (*.csv)")
        if path:
            try:
                export_side_leakage_csv(self._design, path)
                self.statusBar().showMessage(f"Exported side leakage to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def _on_export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Results JSON", "", "JSON Files (*.json)")
        if path:
            try:
                export_results_json(self._design, path)
                self.statusBar().showMessage(f"Exported results to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_all_outputs()

    def _on_about(self):
        QMessageBox.about(self, "About LoudspeakerFEA", "LoudspeakerFEA v0.1.3\n\nFinite Element Analysis augmented desktop application for ceramic magnet woofer motor simulation.")

    def _on_browse_elmer(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select ElmerSolver Executable", "", "Executable Files (*.exe)"
        )
        if path:
            self._design = update_design_parameter(self._design, "elmer_solver_path", path)
            set_elmer_executable_path(path)
            self.statusBar().showMessage(f"Elmer path set to {path}")

    def _on_set_working_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Select Working Directory")
        if path:
            self._design = update_design_parameter(self._design, "working_directory", path)
            set_working_directory(path)
            self.statusBar().showMessage(f"Working directory set to {path}")

    def _on_set_mesh_size_factor(self):
        from PyQt6.QtWidgets import QInputDialog
        val, ok = QInputDialog.getDouble(
            self, "Mesh Size Factor", "Enter mesh size factor (0.1–2.0):",
            self._design.mesh_size_factor, 0.1, 2.0, 2
        )
        if ok:
            self._design = update_design_parameter(self._design, "mesh_size_factor", val)
            self.statusBar().showMessage(f"Mesh size factor set to {val}")

    def _on_set_show_processor(self):
        from PyQt6.QtWidgets import QInputDialog
        items = ["0", "1"]
        val, ok = QInputDialog.getItem(
            self, "Show Processor", "Select:",
            items, self._design.show_processor, False
        )
        if ok:
            self._design = update_design_parameter(self._design, "show_processor", int(val))
            self.statusBar().showMessage(f"Show processor set to {val}")

    def _on_run_elmer(self):
        self.statusBar().showMessage("Running Elmer simulation...")
        try:
            self._design = run_elmer_simulation(self._design, show_window=False)
            self._refresh_all_outputs()
            self.statusBar().showMessage("Elmer simulation complete")
        except Exception as e:
            QMessageBox.critical(self, "Elmer Error", str(e))
            self.statusBar().showMessage("Elmer simulation failed")

    def _sync_inputs_from_design(self):
        """Update all input widgets to match the current design."""
        d = self._design
        self._inp_wire_dia.setValue(d.wire_diameter)
        self._inp_vc_dcr.setValue(d.vc_wire_dcr)
        self._inp_tinsel_dcr.setValue(d.tinsel_wire_dcr)
        self._inp_coil_id.setValue(d.coil_id)
        self._inp_coil_tol.setValue(d.coil_id_tolerance)
        self._inp_former_thick.setValue(d.former_thickness)
        self._inp_former_len.setValue(d.former_length)
        self._inp_num_layers.setValue(d.number_of_layers)
        self._inp_wire_type.setCurrentIndex(d.wire_type - 1)
        self._inp_former_type.setCurrentIndex(d.former_type - 1)
        self._inp_overhang.setValue(d.overhang)
        self._inp_magnet_mat.setCurrentText(d.magnet_material)
        self._inp_inside_gap.setValue(d.inside_gap)
        self._inp_outside_gap.setValue(d.outside_gap)
        self._inp_tp_id.setValue(d.top_plate_id)
        self._inp_tp_od.setValue(d.top_plate_od)
        self._inp_tp_thick.setValue(d.top_plate_thickness)
        self._inp_mag_id.setValue(d.magnet_id)
        self._inp_mag_od.setValue(d.magnet_od)
        self._inp_mag_thick.setValue(d.magnet_thickness)
        self._inp_pole_od.setValue(d.pole_od)
        self._inp_pole_vent.setValue(d.pole_vent_hole)
        self._inp_pole_overhang.setValue(d.pole_overhang)
        self._inp_bp_od.setValue(d.bp_od)
        self._inp_bp_thick.setValue(d.bp_thickness)
        self._inp_vc_offset.setValue(d.vc_offset)
        self._inp_leak_dist.setValue(d.side_leakage_distance)
        self._inp_bl_threshold.setValue(d.bl_threshold_pct)
