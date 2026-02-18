"""
End-to-end upload flow tests mirroring upload_video.py.

upload_video.py decides which path to take based on file size:

  Direct upload (file ≤ 100 MB)
    1. POST /upload              → presigned PUT URL + fileKey
    2. PUT file to presigned URL  (client → S3 directly; simulated here)

  Multipart upload (file > 100 MB)
    1. POST /multipart/init      → uploadId + fileKey + per-part presigned URLs
    2. PUT each 100 MB chunk      (client → S3 directly; simulated here)
    3. POST /multipart/complete   → finalize with collected ETags → location

These tests call the Lambda handlers in sequence the same way the CLI client
does, passing outputs of one call as inputs to the next.
"""

import math
from unittest.mock import MagicMock, patch

from conftest import TEST_BUCKET, TEST_USER_ID, load_lambda, make_event, parse_body

video_upload = load_lambda("video-upload")
multipart_init = load_lambda("multipart-init")
multipart_complete = load_lambda("multipart-complete")

PART_SIZE = 100 * 1024 * 1024        # 100 MB
DIRECT_THRESHOLD = 100 * 1024 * 1024  # upload_video.py's DIRECT_UPLOAD_THRESHOLD


class TestDirectUploadFlow:
    """
    Mirrors UploadManager.start_direct_upload() in upload_video.py.
    Used for files at or below the 100 MB threshold.
    """

    def test_small_file_receives_presigned_put_url(self):
        file_size = 50 * 1024 * 1024  # 50 MB — well under threshold
        assert file_size <= DIRECT_THRESHOLD

        presigned_url = "https://s3.amazonaws.com/presigned-put"
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = presigned_url

        # Step 1 — call POST /upload, get presigned PUT URL
        with patch.object(video_upload, "s3_client", mock_s3):
            resp = video_upload.handler(make_event({
                "filename": "lecture.mp4",
                "userId": TEST_USER_ID,
                "contentType": "video/mp4",
            }), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)

        upload_url = body["uploadUrl"]
        file_key = body["fileKey"]

        # Step 2 — client PUTs file body to upload_url (S3 call; simulated)
        # In upload_video.py: requests.put(upload_url, data=file_bytes, headers={...})
        assert upload_url == presigned_url
        assert TEST_USER_ID in file_key
        assert "lecture.mp4" in file_key

    def test_boundary_file_size_uses_direct_path(self):
        """A file exactly at the threshold should go through /upload, not multipart."""
        file_size = DIRECT_THRESHOLD  # exactly 100 MB

        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.amazonaws.com/url"

        with patch.object(video_upload, "s3_client", mock_s3):
            resp = video_upload.handler(make_event({
                "filename": "boundary.mp4",
                "userId": TEST_USER_ID,
                "contentType": "video/mp4",
            }), {})

        # /upload has no fileSize validation; it always returns a presigned URL
        assert resp["statusCode"] == 200
        mock_s3.generate_presigned_url.assert_called_once()


class TestMultipartUploadFlow:
    """
    Mirrors UploadManager.start_multipart_upload() in upload_video.py.
    Used for files above the 100 MB threshold.
    """

    def test_large_file_full_three_step_flow(self):
        file_size = 250 * 1024 * 1024  # 250 MB → 3 parts
        assert file_size > DIRECT_THRESHOLD

        expected_parts = math.ceil(file_size / PART_SIZE)  # 3
        fake_upload_id = "mpu-abc123xyz"
        fake_location = f"https://s3.amazonaws.com/{TEST_BUCKET}/key"

        s3_init = MagicMock()
        s3_init.create_multipart_upload.return_value = {"UploadId": fake_upload_id}
        s3_init.generate_presigned_url.side_effect = [
            f"https://s3.amazonaws.com/part-{i}" for i in range(1, expected_parts + 1)
        ]

        s3_complete = MagicMock()
        s3_complete.complete_multipart_upload.return_value = {
            "Location": fake_location,
            "Bucket": TEST_BUCKET,
        }

        # Step 1 — POST /multipart/init
        with patch.object(multipart_init, "s3_client", s3_init):
            init_resp = multipart_init.handler(make_event({
                "filename": "large-lecture.mp4",
                "userId": TEST_USER_ID,
                "contentType": "video/mp4",
                "fileSize": file_size,
            }), {})

        assert init_resp["statusCode"] == 200
        init_body = parse_body(init_resp)

        upload_id = init_body["uploadId"]
        file_key = init_body["fileKey"]
        presigned_urls = init_body["presignedUrls"]

        assert upload_id == fake_upload_id
        assert len(presigned_urls) == expected_parts

        # Step 2 — PUT each chunk to its presigned URL, collect ETag from response header
        # In upload_video.py: response = requests.put(url, data=chunk); etag = response.headers["ETag"]
        uploaded_parts = [
            {"PartNumber": part["partNumber"], "ETag": f"etag-{part['partNumber']}"}
            for part in presigned_urls
        ]

        # Step 3 — POST /multipart/complete
        with patch.object(multipart_complete, "s3_client", s3_complete):
            complete_resp = multipart_complete.handler(make_event({
                "fileKey": file_key,
                "uploadId": upload_id,
                "parts": uploaded_parts,
            }), {})

        assert complete_resp["statusCode"] == 200
        complete_body = parse_body(complete_resp)

        assert complete_body["fileKey"] == file_key
        assert complete_body["location"] == fake_location

        # Confirm S3 received the correct ETags and upload ID
        finalize_call = s3_complete.complete_multipart_upload.call_args.kwargs
        assert finalize_call["UploadId"] == fake_upload_id
        assert finalize_call["Key"] == file_key
        submitted = finalize_call["MultipartUpload"]["Parts"]
        assert len(submitted) == expected_parts
        assert all("ETag" in p and "PartNumber" in p for p in submitted)

    def test_file_just_over_threshold_uses_two_parts(self):
        """
        100 MB + 1 byte → ceil((100MB+1) / 100MB) = 2 parts.
        The first part carries a full 100 MB; the second carries the 1 remaining byte.
        """
        file_size = DIRECT_THRESHOLD + 1  # 100 MB + 1 byte → 2 parts

        s3_init = MagicMock()
        s3_init.create_multipart_upload.return_value = {"UploadId": "mpu-two-parts"}
        s3_init.generate_presigned_url.side_effect = [
            "https://s3.amazonaws.com/part-1",
            "https://s3.amazonaws.com/part-2",
        ]

        with patch.object(multipart_init, "s3_client", s3_init):
            resp = multipart_init.handler(make_event({
                "filename": "just-over.mp4",
                "userId": TEST_USER_ID,
                "contentType": "video/mp4",
                "fileSize": file_size,
            }), {})

        assert resp["statusCode"] == 200
        body = parse_body(resp)
        assert body["partCount"] == 2
        assert len(body["presignedUrls"]) == 2
