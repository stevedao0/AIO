# -*- coding: utf-8 -*-
import flet as ft
from flet import Colors, Icons, RoundedRectangleBorder, margin, padding, FontWeight

CARD_RADIUS = 12

def group_tile(icon, title, content, expanded=True):
    return ft.Card(
        elevation=1,
        shape=RoundedRectangleBorder(radius=CARD_RADIUS),
        margin=margin.only(bottom=12),
        content=ft.ExpansionTile(
            initially_expanded=expanded,
            controls=[ft.Container(content=content, padding=padding.all(8))],
            title=ft.Row(
                [ft.Icon(icon, color=Colors.PRIMARY),
                 ft.Text(title, weight=FontWeight.W_600, size=14)],
                spacing=8
            ),
        ),
    )

def sticky_actions(left_controls, right_controls=None):
    row = [ft.Row(left_controls, spacing=8)]
    if right_controls:
        row.append(ft.Row(right_controls, spacing=8))
    return ft.Row(row, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

def status_bar(progress_text: ft.Text, progress_bar: ft.ProgressBar):
    return ft.Row([progress_text, progress_bar], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

def two_pane(left, right, left_expand: int, right_expand: int):
    return ft.Row(
        [
            ft.Container(left, expand=left_expand, padding=padding.only(right=8)),
            ft.Container(right, expand=right_expand, padding=padding.only(left=8)),
        ],
        expand=True,
    )
