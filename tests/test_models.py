from cordless.models import Channel, Guild, Member, Permissions, Role, User


def test_permissions_reads_named_bits():
    perms = Permissions("48")  # manage_channels (0x10) | manage_guild (0x20)
    assert perms.manage_channels
    assert perms.manage_guild
    assert not perms.administrator
    assert not perms.kick_members


def test_permissions_administrator_bit():
    perms = Permissions("8")
    assert perms.administrator


def test_permissions_defaults_to_zero():
    perms = Permissions(None)
    assert perms.value == 0
    assert not perms.administrator


def test_permissions_unknown_name_raises():
    perms = Permissions("8")
    try:
        perms.not_a_real_permission
        assert False, "expected AttributeError"
    except AttributeError:
        pass


def test_permissions_int_conversion():
    perms = Permissions("2147483647")
    assert int(perms) == 2147483647


def test_member_permissions_wrapped():
    member = Member({"nick": "shiv", "permissions": "8"})
    assert isinstance(member.permissions, Permissions)
    assert member.permissions.administrator


def test_member_permissions_missing():
    member = Member({"nick": "shiv"})
    assert member.permissions is None


def test_role_permissions_wrapped():
    role = Role({"id": "1", "name": "Moderator", "permissions": "8589934592"})  # manage_events
    assert role.permissions.manage_events
    assert not role.permissions.administrator


def test_permissions_built_from_kwargs():
    perms = Permissions(manage_guild=True, kick_members=True)
    assert perms.manage_guild
    assert perms.kick_members
    assert not perms.administrator
    assert int(perms) == 0x20 | 0x2


def test_permissions_kwargs_on_top_of_raw_value():
    perms = Permissions("8", manage_guild=True)  # administrator, plus manage_guild
    assert perms.administrator
    assert perms.manage_guild


def test_permissions_kwarg_false_clears_bit():
    perms = Permissions("8", administrator=False)  # started as administrator, turned off
    assert not perms.administrator
    assert int(perms) == 0


def test_permissions_unknown_kwarg_raises():
    try:
        Permissions(not_a_real_permission=True)
        assert False, "expected TypeError"
    except TypeError:
        pass


# --- CDN asset URLs ---


def test_user_avatar_url_from_hash():
    user = User({"id": "80351110224678912", "avatar": "8342729096ea3675442027381ff50dfe"})
    assert (
        user.avatar_url == "https://cdn.discordapp.com/avatars/80351110224678912/8342729096ea3675442027381ff50dfe.png"
    )


def test_user_avatar_url_animated_hash_uses_gif():
    user = User({"id": "1", "avatar": "a_1234567890abcdef1234567890abcdef"})
    assert user.avatar_url == "https://cdn.discordapp.com/avatars/1/a_1234567890abcdef1234567890abcdef.gif"


def test_user_avatar_url_falls_back_to_default_avatar_pomelo():
    user = User({"id": "80351110224678912", "discriminator": "0"})
    assert user.avatar_url == "https://cdn.discordapp.com/embed/avatars/5.png"


def test_user_avatar_url_falls_back_to_default_avatar_legacy_discriminator():
    user = User({"id": "1", "discriminator": "1234"})
    assert user.avatar_url == "https://cdn.discordapp.com/embed/avatars/4.png"


def test_user_banner_url_from_hash():
    user = User({"id": "1", "banner": "abcd1234"})
    assert user.banner_url == "https://cdn.discordapp.com/banners/1/abcd1234.png"


def test_user_banner_url_none_when_unset():
    user = User({"id": "1"})
    assert user.banner_url is None


def test_role_icon_url_from_hash():
    role = Role({"id": "1", "icon": "abcd1234"})
    assert role.icon_url == "https://cdn.discordapp.com/role-icons/1/abcd1234.png"


def test_role_icon_url_none_when_unset():
    role = Role({"id": "1"})
    assert role.icon_url is None


def test_guild_icon_url_from_hash():
    guild = Guild({"id": "1", "icon": "abcd1234"})
    assert guild.icon_url == "https://cdn.discordapp.com/icons/1/abcd1234.png"


def test_guild_icon_url_none_when_unset():
    guild = Guild({"id": "1"})
    assert guild.icon_url is None


def test_guild_banner_url_from_hash():
    guild = Guild({"id": "1", "banner": "abcd1234"})
    assert guild.banner_url == "https://cdn.discordapp.com/banners/1/abcd1234.png"


def test_guild_splash_url_from_hash():
    guild = Guild({"id": "1", "splash": "abcd1234"})
    assert guild.splash_url == "https://cdn.discordapp.com/splashes/1/abcd1234.png"


def test_guild_discovery_splash_url_from_hash():
    guild = Guild({"id": "1", "discovery_splash": "abcd1234"})
    assert guild.discovery_splash_url == "https://cdn.discordapp.com/discovery-splashes/1/abcd1234.png"


# --- mention strings ---


def test_user_mention():
    user = User({"id": "737983831000350731"})
    assert user.mention == "<@737983831000350731>"


def test_role_mention():
    role = Role({"id": "1525899333114003547"})
    assert role.mention == "<@&1525899333114003547>"


def test_channel_mention():
    channel = Channel({"id": "1360544003434745908"})
    assert channel.mention == "<#1360544003434745908>"
