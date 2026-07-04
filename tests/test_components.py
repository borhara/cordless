"""Unit tests for component builders and embed helpers."""
from cordless import (
    ActionRow, Button, ButtonStyle, ChannelSelect, Container,
    Embed, EmbedField, MediaGallery, MentionableSelect, Modal,
    RoleSelect, Section, SelectOption, Separator, StringSelect,
    TextDisplay, TextInput, TextInputStyle, Thumbnail, UserSelect,
)


# --- SelectOption ---

def test_select_option_minimal():
    assert SelectOption("Label", "val").to_dict() == {"label": "Label", "value": "val"}


def test_select_option_full():
    d = SelectOption("Label", "val", description="Desc", default=True).to_dict()
    assert d["description"] == "Desc"
    assert d["default"] is True


# --- Button ---

def test_button_primary():
    d = Button("Click me", custom_id="btn1").to_dict()
    assert d == {"type": 2, "label": "Click me", "custom_id": "btn1", "style": 1}


def test_button_link():
    d = Button("Go", style=ButtonStyle.LINK, url="https://example.com").to_dict()
    assert d["style"] == 5
    assert d["url"] == "https://example.com"
    assert "custom_id" not in d


def test_button_disabled():
    assert Button("X", custom_id="x", disabled=True).to_dict()["disabled"] is True


# --- ActionRow ---

def test_action_row_wraps_buttons():
    d = ActionRow([Button("A", custom_id="a"), Button("B", custom_id="b")]).to_dict()
    assert d["type"] == 1
    assert len(d["components"]) == 2


# --- StringSelect ---

def test_string_select():
    d = StringSelect("color", [SelectOption("One", "1"), SelectOption("Two", "2")],
                     placeholder="Pick one").to_dict()
    assert d["type"] == 3
    assert d["custom_id"] == "color"
    assert d["placeholder"] == "Pick one"
    assert len(d["options"]) == 2


# --- Other select types ---

def test_user_select():
    assert UserSelect("u").to_dict()["type"] == 5


def test_role_select():
    assert RoleSelect("r").to_dict()["type"] == 6


def test_mentionable_select():
    assert MentionableSelect("m").to_dict()["type"] == 7


def test_channel_select():
    d = ChannelSelect("ch", channel_types=[0, 2]).to_dict()
    assert d["type"] == 8
    assert d["channel_types"] == [0, 2]


# --- TextInput / Modal ---

def test_text_input():
    d = TextInput("name_input", "Your name", style=TextInputStyle.SHORT, placeholder="e.g. Alice").to_dict()
    assert d == {"type": 4, "custom_id": "name_input", "label": "Your name", "style": 1, "placeholder": "e.g. Alice"}


def test_modal_wraps_text_inputs_in_action_rows():
    d = Modal("feedback_modal", "Feedback", TextInput("q", "Question")).to_dict()
    assert d["custom_id"] == "feedback_modal"
    assert d["title"] == "Feedback"
    assert d["components"][0]["type"] == 1      # ActionRow
    assert d["components"][0]["components"][0]["type"] == 4  # TextInput


def test_modal_accepts_pre_wrapped_action_rows():
    d = Modal("m", "Title", ActionRow([TextInput("q", "Question")])).to_dict()
    assert d["components"][0]["type"] == 1


# --- Embed ---

def test_embed_minimal():
    d = Embed(title="Hello", description="World", color=0xFF5733).to_dict()
    assert d == {"title": "Hello", "description": "World", "color": 0xFF5733}


def test_embed_all_fields():
    d = (
        Embed(title="T")
        .set_footer("Footer", icon_url="https://i.example.com/icon.png")
        .set_image("https://i.example.com/img.png")
        .set_thumbnail("https://i.example.com/thumb.png")
        .set_author("Author", url="https://example.com", icon_url="https://i.example.com/a.png")
        .add_field("Field", "Value", inline=True)
    ).to_dict()
    assert d["footer"]["text"] == "Footer"
    assert d["image"]["url"] == "https://i.example.com/img.png"
    assert d["thumbnail"]["url"] == "https://i.example.com/thumb.png"
    assert d["author"]["name"] == "Author"
    assert d["fields"][0] == {"name": "Field", "value": "Value", "inline": True}


def test_embed_field():
    assert EmbedField("Name", "Value", inline=True).to_dict() == {"name": "Name", "value": "Value", "inline": True}


# --- UI Kit components ---

def test_text_display():
    assert TextDisplay("Hello world").to_dict() == {"type": 10, "content": "Hello world"}


def test_thumbnail():
    d = Thumbnail("https://example.com/img.png", description="Alt").to_dict()
    assert d["type"] == 11
    assert d["media"]["url"] == "https://example.com/img.png"
    assert d["description"] == "Alt"


def test_separator():
    assert Separator(divider=True, spacing=2).to_dict() == {"type": 14, "divider": True, "spacing": 2}


def test_section_with_accessory():
    d = Section(TextDisplay("Hi"), accessory=Thumbnail("https://example.com/img.png")).to_dict()
    assert d["type"] == 9
    assert d["accessory"]["type"] == 11


def test_container():
    d = Container([TextDisplay("Hi")], accent_color=0xFF0000).to_dict()
    assert d["type"] == 17
    assert d["accent_color"] == 0xFF0000


def test_media_gallery():
    assert MediaGallery({"url": "https://example.com/img.png"}).to_dict()["type"] == 12
