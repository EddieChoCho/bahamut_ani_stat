import click
import pandas as pd
import pkg_resources
import sqlalchemy
from bokeh.io import output_file, save
from bokeh.layouts import column, row
from bokeh.models import (
    CDSView,
    ColumnDataSource,
    CustomJS,
    CustomJSFilter,
    DataTable,
    DateFormatter,
    RangeSlider,
    TableColumn,
    TextInput,
    Toggle,
)
from bokeh.plotting import figure
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql import functions as sql_func

from bahamut_ani_stat.db import models


@click.group(name="plot")
def plot_command_group():
    pass


@plot_command_group.command(name="premium-rate")
@click.argument("db-uri")
@click.argument("output-filename", default="premium-rate.html")
def plot_premium_rate_command(db_uri: str, output_filename: str):
    engine = sqlalchemy.create_engine(db_uri)
    with Session(engine) as session, session.begin():
        stmt = select(models.PremiumRate)
        results = session.execute(stmt).scalars().all()

        data = {row.insert_time: row.premium_rate for row in results}

    pr_series = pd.Series(data)
    pr_series.index = pr_series.index.date
    idx = pd.date_range(pr_series.index.min(), pr_series.index.max())
    pr_series = pr_series.reindex(idx)
    pr_series = pr_series.interpolate(method="pad")

    output_file(filename=output_filename, title="巴哈姆特動畫瘋 - 付費比例")
    p = figure(
        title="巴哈姆特動畫瘋 - 付費比例",
        x_axis_label="記錄時間",
        y_axis_label="付費比例",
        x_axis_type="datetime",
    )
    p.line(pr_series.index, pr_series.values)
    save(p)
    click.echo(f"Export premium plot to {output_filename}")


@plot_command_group.command(name="anime")
@click.argument("db-uri")
@click.argument("output-filename", default="anime.html")
def plot_anime_command(db_uri: str, output_filename: str):
    engine = sqlalchemy.create_engine(db_uri)
    with Session(engine) as session, session.begin():
        stmt = select(models.PremiumRate)
        results = session.execute(stmt).scalars().all()

        stmt = select(models.Anime)
        results = session.execute(stmt).scalars().all()
        column_sources = {
            "sn": [row.sn for row in results],
            "name": [row.name for row in results],
            "release_time": [row.release_time for row in results],
            "upload_hour": [row.upload_hour for row in results],
            "is_new": [row.is_new for row in results],
            "anime_view_counts": [
                row.anime_view_counts[-1].view_count if row.anime_view_counts else -1
                for row in results
            ],
            "anime_scores": [
                row.anime_scores[-1].score if row.anime_scores else -1
                for row in results
            ],
        }

        stmt = select(sql_func.max(models.AnimeViewCount.view_count))
        max_view_count = session.execute(stmt).scalars().first()

    data_source = ColumnDataSource(column_sources)

    output_file(filename=output_filename, title="巴哈姆特動畫瘋 - 所有動畫")

    emit_js = CustomJS(
        args={"data_source": data_source}, code="data_source.change.emit()"
    )
    text_input = TextInput(placeholder="動畫名稱", height_policy="min",)
    text_input.js_on_change("value", emit_js)

    only_new_toggle = Toggle(
        label="只顯示新番",
        button_type="default",
        active=False,
        height_policy="min",
        width_policy="min",
    )
    only_new_toggle.js_on_click(emit_js)

    ignore_wip_toggle = Toggle(
        label="不顯示統計中",
        button_type="default",
        active=False,
        height_policy="min",
        width_policy="min",
    )
    ignore_wip_toggle.js_on_click(emit_js)

    view_counter_silider = RangeSlider(
        start=-1,
        end=max_view_count,
        value=(-1, max_view_count),
        step=1,
        title="觀看人次",
        margin=(2, 10, 5, 10),
    )
    view_counter_silider.js_on_change("value", emit_js)

    score_slider = RangeSlider(
        start=-1, end=10, value=(-1, 10), step=0.1, title="評分", margin=(2, 10, 5, 10)
    )
    score_slider.js_on_change("value", emit_js)

    anime_js_filter = CustomJSFilter(
        args={
            "data_source": data_source,
            "score_slider": score_slider,
            "view_counter_silider": view_counter_silider,
            "only_new_toggle": only_new_toggle,
            "ignore_wip_toggle": ignore_wip_toggle,
            "text_input": text_input,
        },
        code=pkg_resources.resource_string(__name__, "anime_filter.js").decode("utf-8"),
    )
    view = CDSView(source=data_source, filters=[anime_js_filter])

    columns = [
        TableColumn(field="name", title="動畫名稱"),
        TableColumn(field="anime_scores", title="評分"),
        TableColumn(field="anime_view_counts", title="觀看人次"),
        TableColumn(field="is_new", title="是否為新番"),
        TableColumn(field="release_time", title="動畫播出時間", formatter=DateFormatter()),
        TableColumn(field="upload_hour", title="動畫上架時間（新番）"),
        TableColumn(field="sn", title="sn"),
    ]
    data_table = DataTable(
        source=data_source,
        columns=columns,
        editable=True,
        reorderable=True,
        height_policy="max",
        width_policy="max",
        view=view,
    )
    result = column(
        column(row(text_input, only_new_toggle, ignore_wip_toggle), height=50),
        column(row(view_counter_silider, score_slider), height=50),
        data_table,
        sizing_mode="stretch_width",
    )
    save(result)
    click.echo(f"Export anime plot to {output_filename}")
