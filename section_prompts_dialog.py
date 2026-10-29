"""
Interactive Section Prompts & AI Co-Authoring Dialog for SeismicScoutingSuite
Allows prompting the user for initial guidance, operational field notes,
and directives per report section, cross-referencing attached photos, maps, and survey data.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, List, Optional

from report_template_modes import ReportSectionItem, get_default_scouting_sections
from scouting_journal_manager import ScoutingJournalManager
from ai_scout_assistant import AIScoutAssistant


class SectionPromptsDialog(tk.Toplevel):
    """Interactive modal dialog for configuring section-by-section initial prompts and AI guidance."""

    def __init__(
        self,
        parent,
        sections: List[ReportSectionItem],
        on_save_callback: Callable[[Dict[str, str]], None],
        ai_assistant: Optional[AIScoutAssistant] = None,
        project_meta: Optional[Dict] = None
    ):
        super().__init__(parent)
        self.title("AI Report Co-Authoring — Section Prompts & Guidance Wizard")
        self.geometry("980x680")
        self.minsize(850, 550)
        self.configure(bg="#0F172A")
        self.transient(parent)
        self.grab_set()

        self.sections = sections or get_default_scouting_sections()
        self.on_save_callback = on_save_callback
        self.journal_mgr = journal_mgr
        self.ai = ai_assistant or AIScoutAssistant()
        self.project_meta = project_meta or {}
        self.selected_sec_index = 0

        self.build_ui()
        self.populate_section_list()
        self.select_section_by_index(0)

    def build_ui(self):
        # 1. Header Bar
        hdr = tk.Frame(self, bg="#1E293B", padx=14, pady=10)
        hdr.pack(fill="x")

        tk.Label(
            hdr,
            text="Interactive Section Prompts & AI Field Co-Authoring",
            font=("Segoe UI", 13, "bold"),
            fg="#38BDF8",
            bg="#1E293B"
        ).pack(anchor="w")

        tk.Label(
            hdr,
            text="Provide initial field guidance or notes per section. The AI Analyzer synthesizes attached data, photos, and maps.\nIf a section has no attached data or notes, it will be created with a mandatory user-action comment.",
            font=("Segoe UI", 9),
            fg="#94A3B8",
            bg="#1E293B"
        ).pack(anchor="w", pady=(2, 0))

        # 2. Main 2-Pane Body
        body = tk.Frame(self, bg="#0F172A", padx=10, pady=10)
        body.pack(fill="both", expand=True)

        # Left Pane: Section Tree/List
        left_box = tk.LabelFrame(
            body,
            text=" Report Section Hierarchy ",
            font=("Segoe UI", 9, "bold"),
            bg="#1E293B",
            fg="#38BDF8",
            padx=6,
            pady=6
        )
        left_box.pack(side="left", fill="y", padx=(0, 8))

        self.sec_tree = ttk.Treeview(
            left_box,
            columns=("status",),
            show="tree headings",
            height=20,
            selectmode="browse"
        )
        self.sec_tree.heading("#0", text="Section Title")
        self.sec_tree.column("#0", width=240)
        self.sec_tree.heading("status", text="Status")
        self.sec_tree.column("status", width=90, anchor="center")
        self.sec_tree.pack(side="left", fill="both", expand=True)
        self.sec_tree.bind("<<TreeviewSelect>>", self.on_section_selected)

        tree_scroll = ttk.Scrollbar(left_box, orient="vertical", command=self.sec_tree.yview)
        self.sec_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y")

        # Right Pane: Editor & AI Synthesis Preview
        right_box = tk.Frame(body, bg="#0F172A")
        right_box.pack(side="right", fill="both", expand=True)

        # Section Info Header
        info_frame = tk.Frame(right_box, bg="#1E293B", padx=10, pady=8)
        info_frame.pack(fill="x", pady=(0, 8))

        self.lbl_sec_title = tk.Label(
            info_frame,
            text="",
            font=("Segoe UI", 11, "bold"),
            fg="#FFFFFF",
            bg="#1E293B"
        )
        self.lbl_sec_title.pack(anchor="w")

        self.lbl_sec_sources = tk.Label(
            info_frame,
            text="",
            font=("Segoe UI", 9),
            fg="#38BDF8",
            bg="#1E293B",
            wraplength=580,
            justify="left"
        )
        self.lbl_sec_sources.pack(anchor="w", pady=(3, 0))

        # User Prompt / Notes Input
        prompt_box = tk.LabelFrame(
            right_box,
            text=" User Initial Guidance / Field Notes for this Section ",
            font=("Segoe UI", 9, "bold"),
            bg="#1E293B",
            fg="#F4F4F5",
            padx=8,
            pady=6
        )
        prompt_box.pack(fill="x", pady=(0, 8))

        self.txt_prompt = tk.Text(
            prompt_box,
            height=5,
            bg="#0A0F1D",
            fg="#E2E8F0",
            insertbackground="#38BDF8",
            font=("Segoe UI", 9),
            wrap="word",
            relief="flat",
            highlightthickness=1,
            highlightcolor="#38BDF8",
            highlightbackground="#334155"
        )
        self.txt_prompt.pack(fill="x", expand=True)
        self.txt_prompt.bind("<KeyRelease>", self.on_prompt_changed)

        btn_row = tk.Frame(prompt_box, bg="#1E293B")
        btn_row.pack(fill="x", pady=(6, 0))

        self.btn_generate_draft = ttk.Button(btn_row, text="⚡ Generate AI Draft for this Section", command=self.test_ai_section_synthesis)
        self.btn_generate_draft.pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="📖 Pre-fill from Field Journal", command=self.prefill_from_journal).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Pre-fill Default Notes", command=self.prefill_default_notes).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Clear Guidance", command=self.clear_current_prompt).pack(side="left")

        # Live AI Synthesis Preview
        preview_box = tk.LabelFrame(
            right_box,
            text=" Section Prose Preview (AI Synthesis or User Action Comment) ",
            font=("Segoe UI", 9, "bold"),
            bg="#1E293B",
            fg="#F4F4F5",
            padx=8,
            pady=6
        )
        preview_box.pack(fill="both", expand=True)

        self.txt_preview = tk.Text(
            preview_box,
            bg="#0A0F1D",
            fg="#E2E8F0",
            font=("Segoe UI", 9),
            wrap="word",
            relief="flat",
            highlightthickness=1,
            highlightcolor="#38BDF8",
            highlightbackground="#334155"
        )
        self.txt_preview.pack(fill="both", expand=True)

        # 3. Bottom Action Bar
        bottom = tk.Frame(self, bg="#1E293B", padx=14, pady=10)
        bottom.pack(fill="x")

        ttk.Button(
            bottom,
            text="Apply Guidance & Return to Report Studio",
            style="Accent.TButton",
            command=self.save_and_close
        ).pack(side="right", padx=(8, 0))

        ttk.Button(bottom, text="Cancel", command=self.destroy).pack(side="right")

        self.lbl_summary = tk.Label(
            bottom,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg="#10B981",
            bg="#1E293B"
        )
        self.lbl_summary.pack(side="left")

    def populate_section_list(self):
        """Populates the treeview with current sections and statuses."""
        self.sec_tree.delete(*self.sec_tree.get_children())
        for idx, sec in enumerate(self.sections):
            status_text = "Ready" if (sec.user_initial_prompt.strip() or sec.detected_sources) else "Needs Input"
            self.sec_tree.insert(
                "",
                "end",
                iid=str(idx),
                text=sec.title,
                values=(status_text,)
            )
        self._update_summary_stats()

    def select_section_by_index(self, idx: int):
        if 0 <= idx < len(self.sections):
            self.selected_sec_index = idx
            self.sec_tree.selection_set(str(idx))
            self.sec_tree.see(str(idx))
            self.load_section_into_editor(self.sections[idx])

    def on_section_selected(self, event):
        sel = self.sec_tree.selection()
        if sel:
            idx = int(sel[0])
            self.save_current_editor_state()
            self.selected_sec_index = idx
            self.load_section_into_editor(self.sections[idx])

    def load_section_into_editor(self, sec: ReportSectionItem):
        self.lbl_sec_title.configure(text=f"{sec.title} ({sec.category})")

        sources_text = "Attached Sources: " + (", ".join(sec.detected_sources) if sec.detected_sources else "None detected")
        self.lbl_sec_sources.configure(text=sources_text)

        self.txt_prompt.delete("1.0", "end")
        if sec.user_initial_prompt:
            self.txt_prompt.insert("1.0", sec.user_initial_prompt)

        self.txt_preview.delete("1.0", "end")
        if sec.generated_content:
            self.txt_preview.insert("1.0", sec.generated_content)
        elif not sec.user_initial_prompt.strip() and not sec.detected_sources:
            self.txt_preview.insert(
                "1.0",
                "[ACTION REQUIRED: This section needs to be written by the user. "
                "No relevant field measurements or attached data files were detected for this topic.]"
            )
        else:
            self.txt_preview.insert("1.0", f"(Click 'Generate AI Draft' to preview AI synthesis for {sec.title})")

    def save_current_editor_state(self):
        if 0 <= self.selected_sec_index < len(self.sections):
            sec = self.sections[self.selected_sec_index]
            sec.user_initial_prompt = self.txt_prompt.get("1.0", "end-1c").strip()
            # Update treeview status
            st = "Ready" if (sec.user_initial_prompt or sec.detected_sources) else "Needs Input"
            self.sec_tree.item(str(self.selected_sec_index), values=(st,))
            self._update_summary_stats()

    def on_prompt_changed(self, event):
        self.save_current_editor_state()

    def clear_current_prompt(self):
        self.txt_prompt.delete("1.0", "end")
        self.save_current_editor_state()
        sec = self.sections[self.selected_sec_index]
        if not sec.detected_sources:
            self.txt_preview.delete("1.0", "end")
            self.txt_preview.insert(
                "1.0",
                "[ACTION REQUIRED: This section needs to be written by the user. "
                "No relevant field measurements or attached data files were detected for this topic.]"
            )

    def prefill_from_journal(self):
        """Pre-fills current section prompt using field thoughts recorded in journal."""
        sec = self.sections[self.selected_sec_index]
        if self.journal_mgr:
            entries = self.journal_mgr.get_entries_by_section(sec.section_id)
            if entries:
                lines = [f"Field Scouting Observations for {sec.title}:"]
                for e in entries:
                    gps_str = f" [GPS: {e.lat:.5f}°N, {e.lon:.5f}°E]" if (e.lat and e.lon) else ""
                    lines.append(f"• ({e.timestamp}){gps_str} {e.text}")
                content = "\n".join(lines)
                self.txt_prompt.delete("1.0", "end")
                self.txt_prompt.insert("1.0", content)
                self.save_current_editor_state()
                return

        # Fallback to standard defaults if no journal notes exist
        self.prefill_default_notes()

    def prefill_all_from_journal(self):
        """Pre-fills all 14 section prompts from available journal entries."""
        if not self.journal_mgr or not self.journal_mgr.entries:
            import tkinter.messagebox as mb
            ans = mb.askyesno("No Journal Entries", "No daily field thoughts found in journal for this project. Would you like to pre-fill with standard GDAD defaults instead?", parent=self)
            if ans:
                for idx in range(len(self.sections)):
                    self.selected_sec_index = idx
                    self.prefill_default_notes()
                self.select_section_by_index(0)
            return

        synthesized = self.journal_mgr.synthesize_section_prompts()
        applied_count = 0
        for s in self.sections:
            if s.section_id in synthesized:
                s.user_initial_prompt = synthesized[s.section_id]
                applied_count += 1

        self.select_section_by_index(self.selected_sec_index)
        self._update_summary_stats()
        import tkinter.messagebox as mb
        mb.showinfo("Prompts Pre-filled", f"Successfully pre-filled {applied_count} sections using field journal observations!", parent=self)

    def prefill_default_notes(self):
        sec = self.sections[self.selected_sec_index]
        defaults = {
            "sec_01_overview": "Focus on desert concession limits, Ain el Abd 1970 datum, and seasonal weather constraints.",
            "sec_03_access": "Highlight 450 km of tracked reconnaissance and mandatory 15 PSI tire deflation in coastal sabkha.",
            "sec_05_comms": "Emphasize 24/7 satellite IVMS tracking, VHF crew channels, and Garmin inReach SOS messaging.",
            "sec_08_permitting": "Note requirement for written crossing permits from Ministry of Transport and 50m GDAD pipeline buffer.",
            "sec_10_hospitals": "Confirm dedicated primary medevac route to nearest General Hospital (under 60 min) and helicopter LZ.",
            "sec_11_difficulties": "Detail treacherous soft sabkha flats, dune crest crossings, and high-voltage power line crossings.",
            "sec_13_conclusion": "State unequivocal survey viability under strict adherence to recommended engineering controls."
        }
        note = defaults.get(sec.section_id, f"Field observations and operational directives for {sec.title}.")
        self.txt_prompt.delete("1.0", "end")
        self.txt_prompt.insert("1.0", note)
        self.save_current_editor_state()

    def test_ai_section_synthesis(self):
        sec = self.sections[self.selected_sec_index]
        self.save_current_editor_state()

        if not sec.user_initial_prompt.strip() and not sec.detected_sources:
            self.txt_preview.delete("1.0", "end")
            self.txt_preview.insert(
                "1.0",
                "[ACTION REQUIRED: This section needs to be written by the user. "
                "No relevant field measurements or attached data files were detected for this topic.]"
            )
            return

        prospect = self.project_meta.get('prospect_name', 'Prospect Area')
        crew = self.project_meta.get('crew_name', 'Crew S-86')

        prompt = (
            f"You are a Senior Geomatics Specialist and Chief Surveyor writing a formal Saudi Aramco Preliminary Digital Scouting Report.\n"
            f"Section: {sec.title} ({sec.category})\n"
            f"Prospect: {prospect}, Crew: {crew}\n"
            f"Attached Data Sources: {', '.join(sec.detected_sources)}\n"
            f"User Guidance / Notes: {sec.user_initial_prompt}\n\n"
            f"Write detailed, publication-ready technical prose adhering strictly to Saudi Aramco GDAD-SL-012R03 specifications. "
            f"Use formal industry terminology, active engineering controls, and specific operational directives."
        )

        # Update button state and preview placeholder
        if hasattr(self, 'btn_generate_draft'):
            self.btn_generate_draft.configure(text="⏳ Generating AI Draft...", state="disabled")
        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("1.0", "Analyzing attached survey data, GIS sources, and drafting technical prose...")

        def _worker():
            try:
                res = self.ai.query(prompt, temperature=0.3)
                draft_text = ""
                if res and res.get("text"):
                    draft_text = res["text"]
                else:
                    draft_text = (
                        f"Technical Specifications for {sec.title} ({prospect}):\n\n"
                        f"Field reconnaissance conducted by {crew} verified operational parameters based on {len(sec.detected_sources)} attached data sources.\n"
                        f"{sec.user_initial_prompt}"
                    )
            except Exception as ex:
                draft_text = f"Error during synthesis: {ex}\n\nField observations:\n{sec.user_initial_prompt}"

            def _on_done():
                sec.generated_content = draft_text
                self.txt_preview.delete("1.0", "end")
                self.txt_preview.insert("1.0", draft_text)
                if hasattr(self, 'btn_generate_draft'):
                    self.btn_generate_draft.configure(text="⚡ Generate AI Draft for this Section", state="normal")
                self._update_summary_stats()

            self.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _update_summary_stats(self):
        ready_count = sum(1 for s in self.sections if (s.user_initial_prompt.strip() or s.detected_sources))
        action_count = len(self.sections) - ready_count
        self.lbl_summary.configure(
            text=f"Sections with Data/Guidance: {ready_count}/{len(self.sections)}  |  User-Action Pending: {action_count}"
        )

    def save_and_close(self):
        self.save_current_editor_state()
        prompts_dict = {s.section_id: s.user_initial_prompt for s in self.sections if s.user_initial_prompt.strip()}
        if self.on_save_callback:
            self.on_save_callback(prompts_dict)
        self.destroy()

