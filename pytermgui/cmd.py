"""
The command-line module of the library.

There are some simple utilities included, and a playground for some
of the interesting parts of pytermgui.

See `ptg --help` for more information.
"""

from __future__ import annotations

import sys
from random import randint
from itertools import zip_longest
from abc import ABC, abstractmethod
from typing import Any, Optional, Type
from argparse import ArgumentParser, Namespace

from . import (
    MarkupSyntaxError,
    # prettify_markup,
    MarkupFormatter,
    WindowManager,
    real_length,
    YamlLoader,
    get_widget,
    InputField,
    Container,
    Splitter,
    terminal,
    markup,
    Window,
    Button,
    Label,
    boxes,
    keys,
)

__all__ = ["Application"]


def _get_key_name(key: str) -> str:
    """Get canonical name of a key"""

    name = keys.get_name(key)
    if name is not None:
        return str("keys." + name)

    return ascii(key)


class Application(ABC):
    """A class representing an application"""

    title: str
    description: str
    standalone: bool = False

    def __init__(self, manager: WindowManager) -> None:
        """Initialize object"""

        self.manager = manager

    @staticmethod
    def _update_widgets(window: Window, items: list[Any]) -> None:
        """Update window widgets, using auto() method for each"""

        window.set_widgets([])
        for item in items:
            window += item

    @abstractmethod
    def finish(self, window: Window) -> None:
        """Print output information on Application finish

        This is called by the main method after self.manager exits.

        In order to support `standalone` mode, the Application should
        call `_request_exit()` once it is done with its duty. This method
        is called directly after."""

    @abstractmethod
    def construct_window(self) -> Window:
        """Construct an application window"""

    def _request_exit(self) -> None:
        """Send a request to the manager parent to stop execution"""

        self.manager.stop()

    def _get_base_window(self, **attrs: Any) -> Window:
        """Get window with basic & universal settings applied"""

        if "title" not in attrs:
            attrs["title"] = " [bold wm-title]" + self.title + " "

        return Window(**attrs)


class LauncherApplication(Application):
    """Application that launches other apps"""

    title = "Launcher"
    description = "Launch other apps"

    def __init__(self, manager: WindowManager, apps: list[Type[Application]]) -> None:
        """Initialize object"""

        super().__init__(manager)

        instantiated_apps: list[Application] = []
        for app in apps:
            instantiated_apps.append(app(manager))

        self.apps = instantiated_apps

    def finish(self, _: Window) -> None:
        """Do nothing on finish"""

    def construct_window(self) -> Window:
        """Construct an application window"""

        window = self._get_base_window(width=30, is_noblur=False) + ""
        manager = self.manager

        for app in self.apps:
            button = Button(app.title)
            button.onclick = lambda *_, button=button: manager.add(
                button.app.construct_window()
            )
            button.app = app
            window += button

        window += ""
        window += Label("[247 italic]> Choose an app to run", parent_align=0)

        assert isinstance(window, Window)
        return window


class GetchApplication(Application):
    """Application for the getch() utility"""

    title = "Getch"
    description = "See your keypresses"

    def _key_callback(self, window: Window, key: str) -> bool:
        """Edit `window` state if `key` is pressed"""

        # Don't display mouse codes
        if (
            self.manager.mouse_translator is not None
            and self.manager.mouse_translator(key) is not None
        ):
            return True

        name = _get_key_name(key)
        items = [
            "[wm-title]Your output",
            "",
            {"[wm-section]key": name},
            {"[wm-section]len()": str(len(key))},
            {"[wm-section]real_length()": str(real_length(key))},
        ]

        window.forced_width = 40
        self._update_widgets(window, items)

        if self.standalone:
            self._request_exit()
            return True

        assert window.manager is not None
        window.manager.print()
        return True

    def finish(self, window: Window) -> None:
        """Dump getch() output to stdout on finish"""

        for line in window.get_lines():
            print(line)

    def construct_window(self) -> Window:
        """Construct an application window"""

        window = self._get_base_window(is_modal=True) + "[wm-title]Press any key..."
        window.bind(
            keys.ANY_KEY, self._key_callback, description="Read key & update window"
        )
        window.center()

        assert isinstance(window, Window)
        return window


class MarkupApplication(Application):
    """Application for the markup parsing methods"""

    title = "MarkApp"
    description = "Play around with markup in this interactive editor."

    @staticmethod
    def _get_tokens() -> list[Label]:
        """Get all tokens using the parser"""

        tokens: list[Label] = []
        for token in markup.tags:
            tokens.append(Label(f"[{token}]{token}", parent_align=0))

        return tokens

    @staticmethod
    def _update_value(output: Label, field: InputField) -> None:
        """Update output value

        This shows parsed markup if parsing succeeded, SyntaxError otherwise."""

        try:
            markup.parse(field.value)
            output.value = field.value
        except MarkupSyntaxError as error:
            output.value = "[210 bold]SyntaxError:[/] " + error.escape_message()

    @staticmethod
    def _style_wrapper(_: int, item: str) -> str:
        """Catch MarkupSyntaxError"""

        try:
            # TODO: Reintroduce prettify_markup

            # This method *always* returns str, but Mypy doesn't see that.
            # return str(prettify_markup(item))
            return item

        except MarkupSyntaxError:
            return item

    @staticmethod
    def _define_colors(*_: Any) -> None:
        """Re-generate colors for guide"""

        def _random_hex() -> str:
            """Return a random hex number"""

            randcol = lambda: randint(0, 255)
            return "#" + "".join(f"{randcol():02x}" for _ in range(3))

        markup.alias("demo-255", str(randint(0, 255)))
        markup.alias("demo-hex", _random_hex())
        markup.alias("demo-rgb", _random_hex())

    def finish(self, window: Window) -> None:
        """Dump output markup to stdout on finish"""

        if window.manager is None:
            return

        window.manager.stop()

        # print(prettify_markup(window.output_label.value))
        print(window.output_label.value)

    def construct_window(self) -> Window:
        """Construct an application window"""

        def dump(window: Window) -> None:
            """Dump lines of window and exit program"""

            with open("dump", "w", encoding="utf8") as file:
                file.write("\n".join(window.get_lines()))

            sys.exit()

        tokens = self._get_tokens()
        self._define_colors()

        colors = [
            "[demo-255]0-255",
            "[demo-hex]#rrggbb",
            "[demo-rgb]rrr;ggg;bbb",
            "",
            "[inverse demo-255]@0-255",
            "[inverse demo-hex]@#rrggbb",
            "[inverse demo-rgb]@rrr;ggg;bbb",
        ]

        corners = Container.chars["corner"]
        assert isinstance(corners, list)
        corners = corners.copy()
        corners[0] += " [wm-title]tokens[/] "
        corners[1] = " [wm-title]colors[60] " + corners[1]

        guide = Container(forced_width=60).set_char("corner", corners)

        for token, color in zip_longest(tokens, colors, fillvalue=""):
            guide += {token: color}

        custom_tags = Container(forced_width=56)
        for tag, _ in sorted(
            markup.user_tags.items(), key=lambda item: len(item[0] + item[1])
        ):
            custom_tags += Label(
                f"[{tag}]{tag}[/fg /bg /]: [!expand({tag})]{tag}",
                parent_align=0,
            )
        guide += custom_tags

        window = (
            self._get_base_window(resizable=True)
            + Container(Label(parent_align=0, id="output_label"), forced_width=60)
            + guide
            + Label(
                "[247 italic]> Tip: Press CTRL_R to randomize colors", parent_align=0
            )
            + ""
            + InputField(id="input_field").set_style("fill", self._style_wrapper)
        )

        output = get_widget("output_label")
        assert isinstance(output, Label)
        field = get_widget("input_field")
        assert isinstance(field, InputField)

        window.output_label = output

        field.bind(
            keys.ANY_KEY,
            lambda field, _, output=output: self._update_value(output, field),
        )

        window.bind(
            keys.CTRL_R,
            self._define_colors,
            description="Randomize colors in the guide",
        )

        window.bind(
            keys.CTRL_P,
            lambda *_: dump(window),
            description="Dump window lines and exit",
        )

        if self.standalone:
            field.bind(keys.RETURN, lambda *_: self._request_exit())

        window.center()
        window.select(0)
        return window


# class HelperApplication(Application):
#     """Application class to show all currently-active bindings"""
#
#     title = "Help"
#     description = "See all current bindings"
#
#     def finish(self, window: Window) -> None:
#         """Do nothing on finish"""
#
#     def construct_window(self) -> Window:
#         """Construct an application window"""
#
#         window = self._get_base_window(width=50) + "[wm-title]Current bindings" + ""
#
#         bindings = list(self.manager.bindings)
#
#         if self.manager.focused is not None:
#             bindings += list(self.manager.focused.bindings)
#
#         # Convert keycode into key name
#         for i, binding in enumerate(bindings):
#             binding_mutable = list(binding)
#             binding_mutable[0] = _get_key_name(binding[0]).strip("'")
#             bindings[i] = tuple(binding_mutable)
#
#         # Sort keys according to key name length
#         bindings.sort(key=lambda item: real_length(item[0]))
#
#         for (key, _, description) in bindings:
#             window += Label("[wm-section]" + key + ": ", parent_align=0)
#             window += Label(description, padding=2, parent_align=0)
#             window += ""
#
#         window.bind(keys.ESC, lambda *_: window.close())
#
#         return window.center()


def run_wm(args: Namespace) -> None:
    """Run WindowManager using args"""

    # This is used for finding Application from arguments
    app_mapping = {"getch": GetchApplication, "markapp": MarkupApplication}

    window: Optional[Window] = None

    with WindowManager() as manager:

        # Define styles
        markup.alias("wm-title", "210")
        boxes.SINGLE.set_chars_of(Container)
        boxes.DOUBLE_TOP.set_chars_of(Window)

        style = MarkupFormatter("[60]{item}")
        for widget in [Window, Container]:
            widget.set_style("border", style)
            widget.set_style("corner", style)

        Splitter.set_style("separator", style)
        Splitter.set_char("separator", " " + boxes.SINGLE.borders[0])
        InputField.set_style("cursor", MarkupFormatter("[@72]{item}"))

        # helper = HelperApplication(manager)

        # Setup bindings
        manager.bind(
            "*", lambda *_: manager.show_targets(), description="Show all mouse targets"
        )

        manager.bind(
            keys.CTRL_W,
            lambda *_: manager.focused.close() if manager.focused is not None else None,
            description="Close focused window",
        )

        # manager.bind(
        #     "?",
        #     lambda *_: manager.add(helper.construct_window()),
        #     description="Show all active bindings",
        # )

        # Run with a launcher
        if len(sys.argv) == 1:
            launcher = LauncherApplication(manager, list(app_mapping.values()))
            manager.add(launcher.construct_window())

        # Run as standalone app
        if args.app:
            app = app_mapping[args.app.lower()](manager)
            app.standalone = True

            window = app.construct_window()
            manager.add(window)

        manager.run()

        # Run finish callback on standalone apps
        if window is not None:
            app.finish(window)


def main() -> None:
    """Main method"""

    parser = ArgumentParser(
        description="Command line interface & demo for some utilities related to TUI development."
    )

    parser.add_argument(
        "--app",
        type=str.lower,
        help="launch an app in standalone mode.",
        metavar="{Getch, MarkApp}",
        choices=["getch", "markapp"],
    )

    parser.add_argument(
        "-g", "--getch", help="launch Getch app in standalone mode", action="store_true"
    )

    parser.add_argument(
        "-m", "--markapp", help="launch MarkApp in standalone mode", action="store_true"
    )

    parser.add_argument(
        "-s",
        "--size",
        help="output current terminal size in WxH format",
        action="store_true",
    )

    parser.add_argument("-f", "--file", help="interpret YAML file")
    parser.add_argument(
        "--print-only",
        help="don't run YAML WindowManager, only print it",
        action="store_true",
    )

    args = parser.parse_args()

    if args.size:
        print(f"{terminal.width}x{terminal.height}")
        return

    if args.file:
        loader = YamlLoader()
        with open(args.file, "r", encoding="utf8") as file:
            namespace = loader.load(file)

        with WindowManager() as manager:
            for widget in namespace.widgets.values():
                assert isinstance(widget, Window)
                manager.add(widget)

            if args.print_only:
                manager.print()
                return

            manager.run()
        return

    if args.getch:
        args.app = "getch"

    if args.markapp:
        args.app = "markapp"

    run_wm(args)


if __name__ == "__main__":
    main()
