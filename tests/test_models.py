from cordless.models import Member, Permissions, Role


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
