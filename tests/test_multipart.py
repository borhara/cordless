"""_multipart.py: Content-Disposition header construction for file uploads."""

from cordless._multipart import build_form_multipart_body, build_multipart_body, parse_multipart_payload


def test_build_multipart_body_escapes_quote_in_filename():
    """A `"` in a filename must not be able to close the filename= value
    early and inject extra header content into the multipart body."""
    body, _ = build_multipart_body({}, [('evil".txt\r\nX-Injected: yes', b"data")])

    assert b'filename="evil\\".txt' in body
    assert b"X-Injected: yes\r\n\r\n" not in body
    assert b"\r\nX-Injected" not in body


def test_build_multipart_body_strips_crlf_from_filename():
    """CRLF in a filename must not be able to terminate the header line
    early and start a forged header or multipart boundary."""
    body, _ = build_multipart_body({}, [("a\r\n--boundary\r\nb.txt", b"data")])

    assert b"\r\n--boundary\r\n" not in body
    assert b'filename="a--boundaryb.txt"' in body


def test_build_multipart_body_round_trips_normal_filenames():
    body, _ = build_multipart_body({"content": "hi"}, [("report.pdf", b"data")])

    assert b'filename="report.pdf"' in body
    assert parse_multipart_payload(body) == {"content": "hi"}


def test_build_form_multipart_body_escapes_field_name_and_filename():
    body, _ = build_form_multipart_body({'field"1': "v"}, "file", 'evil".png', b"data")

    assert b'name="field\\"1"' in body
    assert b'filename="evil\\".png"' in body
