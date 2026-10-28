from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import MinistryAccessRequest, User
from resources.models import Resource

from .models import Activity, GalleryAlbum, GalleryPhoto, Ministry, MinistryAnnouncement, MinistryInquiry, MinistryMemberSpotlight


def test_jpeg(name="IMG_1234.jpg", size=(3000, 2200)):
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", size, (48, 92, 138)).save(output, format="JPEG", quality=98)
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/jpeg")


class PublicMinistryTests(TestCase):
    def setUp(self):
        self.ministry = Ministry.objects.create(
            name="Youth & Kids Ministry", slug="youth-kids-ministry", description="Faith and discipleship."
        )

    def test_public_pages_do_not_require_login(self):
        for url in (
            reverse("public_ministries:list"),
            reverse("public_ministries:detail", args=[self.ministry.slug]),
            reverse("public_ministries:contact", args=[self.ministry.slug]),
            reverse("public_ministries:join", args=[self.ministry.slug]),
            reverse("core:public_activities"),
            reverse("public_resources:list"),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_farm_day_story_is_published_in_activities(self):
        album = GalleryAlbum.objects.create(
            ministry=self.ministry, title="Farm Day at Pettit Creek Farms",
            slug="farm-day-at-pettit-creek-farms", event_date="2026-10-24",
            location="Pettit Creek Farms", description="Animals, games, and fellowship.",
        )
        GalleryPhoto.objects.create(
            ministry=self.ministry, album=album, caption="Farm Day welcome", occasion="outdoor",
            year=2026, static_path="activity-images/farm-day/farm-day-01.webp",
            content_type="image/webp", filename="farm-day-01.webp",
        )
        response = self.client.get(reverse("core:public_activities"))
        self.assertContains(response, "Farm Day at Pettit Creek Farms")
        self.assertContains(response, "October 24, 2026")
        self.assertContains(response, "farm-day-01.webp")
        self.assertContains(response, "View all 1 photos")

    def test_choir_and_youth_photos_appear_on_public_pages(self):
        choir = Ministry.objects.create(name="Choir Ministry", slug="choir-ministry")
        women = Ministry.objects.create(name="Women Service", slug="women-service")
        listing = self.client.get(reverse("public_ministries:list"))
        self.assertContains(listing, "KidsYouth4.jpg")
        self.assertContains(listing, "choir4.jpg")
        youth_detail = self.client.get(self.ministry.get_public_url())
        self.assertContains(youth_detail, "kidsYouth1.jpg")
        self.assertContains(youth_detail, "KidsYouth2.jpg")
        choir_detail = self.client.get(choir.get_public_url())
        self.assertContains(choir_detail, "choir1.jpg")
        self.assertContains(choir_detail, "choir3.jpg")
        self.assertContains(self.client.get(women.get_public_url()), "women1.jpg")

    def test_public_ministry_page_has_member_placeholders(self):
        response = self.client.get(self.ministry.get_public_url())
        self.assertContains(response, "Meet the ministry")
        self.assertContains(response, "Our ministry family", count=3)

    def test_leader_creates_public_member_spotlight_with_optional_photo(self):
        leader = User.objects.create_user("spotlightlead", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        self.client.force_login(leader)
        response = self.client.post(reverse("ministries:member_spotlight_new", args=[self.ministry.slug]), {
            "display_name": "Sara T.", "role": "Youth volunteer",
            "short_message": "Serving together has helped my faith grow.",
            "sort_order": "1", "is_public": "on", "image": test_jpeg("sara-portrait.jpg"),
        })
        spotlight = MinistryMemberSpotlight.objects.get(display_name="Sara T.")
        self.assertRedirects(response, f"{self.ministry.get_absolute_url()}#member-spotlights")
        self.assertTrue(spotlight.image_blob)
        self.assertLess(len(spotlight.image_blob), 1024 * 1024)
        public = self.client.get(self.ministry.get_public_url())
        self.assertContains(public, "Sara T.")
        self.assertContains(public, "Serving together has helped my faith grow.")
        image = self.client.get(spotlight.get_image_url())
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image["Content-Type"], "image/jpeg")

    def test_draft_member_spotlight_and_image_are_not_public(self):
        spotlight = MinistryMemberSpotlight.objects.create(
            ministry=self.ministry, display_name="Draft Member", short_message="Not approved yet.",
            image_blob=b"private-image", image_content_type="image/jpeg", is_public=False,
        )
        public = self.client.get(self.ministry.get_public_url())
        self.assertNotContains(public, "Draft Member")
        self.assertEqual(self.client.get(spotlight.get_image_url()).status_code, 404)

    def test_leader_uploads_captioned_grouped_gallery_photo(self):
        leader = User.objects.create_user("gallerylead", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        self.client.force_login(leader)
        photo_file = SimpleUploadedFile(
            "conference.png", b"\x89PNG\r\n\x1a\n" + b"gallery-image", content_type="image/png"
        )
        response = self.client.post(reverse("ministries:gallery", args=[self.ministry.slug]), {
            "caption": "Youth conference worship", "occasion": "conference", "year": "2026",
            "is_public": "on", "image": photo_file,
        })
        self.assertRedirects(response, reverse("ministries:gallery", args=[self.ministry.slug]))
        photo = GalleryPhoto.objects.get(caption="Youth conference worship")
        public = self.client.get(reverse("core:public_activities"))
        self.assertContains(public, "Conference")
        self.assertContains(public, "2026")
        self.assertContains(public, "Youth conference worship")
        image = self.client.get(photo.get_image_url())
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image["Content-Type"], "image/png")
        other = Ministry.objects.create(name="Other Ministry")
        self.assertEqual(self.client.get(reverse("ministries:gallery", args=[other.slug])).status_code, 403)

    def test_photo_gallery_is_available_from_activity_portal(self):
        leader = User.objects.create_user("hublead", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        self.client.force_login(leader)
        portal = self.client.get(reverse("core:portal"))
        self.assertContains(portal, "Photo gallery")
        self.assertEqual(self.client.get(reverse("ministries:gallery_hub")).status_code, 200)
        photo_file = SimpleUploadedFile(
            "outdoor.jpg", b"\xff\xd8\xff" + b"gallery-image", content_type="image/jpeg"
        )
        response = self.client.post(reverse("ministries:gallery_hub"), {
            "ministry": self.ministry.pk, "caption": "Children outdoors", "occasion": "outdoor",
            "year": "2026", "is_public": "on", "image": photo_file,
        })
        self.assertRedirects(response, reverse("ministries:gallery_hub"))
        self.assertTrue(GalleryPhoto.objects.filter(caption="Children outdoors", ministry=self.ministry).exists())

    def test_leader_can_create_edit_and_delete_gallery_album(self):
        leader = User.objects.create_user("albumlead", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        self.client.force_login(leader)
        response = self.client.post(reverse("ministries:gallery_album_new"), {
            "ministry": self.ministry.pk, "title": "Autumn Fellowship", "event_date": "2026-10-24",
            "location": "Pettit Creek Farms", "description": "A joyful day.", "is_public": "on",
        })
        self.assertRedirects(response, reverse("ministries:gallery_hub"))
        album = GalleryAlbum.objects.get(title="Autumn Fellowship")
        self.assertEqual(album.ministry, self.ministry)
        response = self.client.post(reverse("ministries:gallery_album_edit", args=[album.pk]), {
            "ministry": self.ministry.pk, "title": "Farm Fellowship", "event_date": "2026-10-24",
            "location": "Pettit Creek Farms", "description": "Updated.", "is_public": "on",
        })
        self.assertRedirects(response, reverse("ministries:gallery_hub"))
        album.refresh_from_db()
        self.assertEqual(album.title, "Farm Fellowship")
        self.assertRedirects(
            self.client.post(reverse("ministries:gallery_album_delete", args=[album.pk])),
            reverse("ministries:gallery_hub"),
        )
        self.assertFalse(GalleryAlbum.objects.filter(pk=album.pk).exists())

    def test_batch_upload_optimizes_and_adds_photo_to_album(self):
        leader = User.objects.create_user("batchlead", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        album = GalleryAlbum.objects.create(
            ministry=self.ministry, title="Autumn Fellowship", event_date="2026-10-24",
            is_public=True, created_by=leader,
        )
        self.client.force_login(leader)
        response = self.client.post(reverse("ministries:gallery_batch_upload"), {
            "ministry": self.ministry.pk, "album": album.pk, "occasion": "outdoor",
            "year": "2026", "is_public": "on", "caption": "Autumn Fellowship — Photo 1",
            "image": test_jpeg(),
        })
        self.assertEqual(response.status_code, 201)
        photo = album.photos.get()
        self.assertEqual(photo.caption, "Autumn Fellowship — Photo 1")
        self.assertEqual(photo.content_type, "image/jpeg")
        self.assertLess(len(photo.image_blob), 1024 * 1024)
        self.assertTrue(photo.is_public)

    def test_batch_upload_cannot_use_another_ministry_album(self):
        leader = User.objects.create_user("restrictedbatch", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        other = Ministry.objects.create(name="Other Ministry")
        album = GalleryAlbum.objects.create(ministry=other, title="Private team album", is_public=True)
        self.client.force_login(leader)
        response = self.client.post(reverse("ministries:gallery_batch_upload"), {
            "ministry": self.ministry.pk, "album": album.pk, "occasion": "outdoor", "year": "2026",
            "image": test_jpeg(),
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(GalleryPhoto.objects.filter(album=album).exists())

    def test_ministry_leader_can_attach_photo_to_activity(self):
        leader = User.objects.create_user("activityphoto", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        self.client.force_login(leader)
        photo_file = SimpleUploadedFile(
            "bible-study.jpg", b"\xff\xd8\xff" + b"activity-image", content_type="image/jpeg"
        )
        response = self.client.post(reverse("ministries:activity_new", args=[self.ministry.slug]), {
            "title": "Youth Bible study", "kind": "class", "date": "2026-10-25",
            "attendance": "18", "volunteer_hours": "2", "summary": "Studied together.",
            "is_public": "on", "image": photo_file, "image_caption": "Youth studying the Bible",
        })
        self.assertRedirects(response, self.ministry.get_absolute_url())
        activity = Activity.objects.get(title="Youth Bible study")
        photo = activity.gallery_photos.get()
        self.assertEqual(photo.ministry, self.ministry)
        self.assertTrue(photo.is_public)
        self.assertContains(self.client.get(reverse("core:public_activities")), "Youth studying the Bible")

    def test_contact_and_join_requests_are_saved_without_privileges(self):
        for kind in ("contact", "join"):
            response = self.client.post(
                reverse(f"public_ministries:{kind}", args=[self.ministry.slug]),
                {"name": "Visitor", "email": "visitor@example.com", "area_interest": "Community service",
                 "message": "Please contact me."},
            )
            self.assertRedirects(response, self.ministry.get_public_url())
        self.assertEqual(MinistryInquiry.objects.filter(ministry=self.ministry).count(), 2)
        self.assertEqual(set(MinistryInquiry.objects.values_list("status", flat=True)), {"pending"})
        self.assertEqual(MinistryInquiry.objects.get(kind="join").area_interest, "Community service")

    def test_only_published_announcements_are_public(self):
        MinistryAnnouncement.objects.create(
            ministry=self.ministry, title="Draft private", body="Not ready", status="draft"
        )
        MinistryAnnouncement.objects.create(
            ministry=self.ministry, title="Published notice", body="Ready", status="published"
        )
        response = self.client.get(self.ministry.get_public_url())
        self.assertContains(response, "Published notice")
        self.assertNotContains(response, "Draft private")

    def test_registration_access_request_never_elevates_user(self):
        response = self.client.post(reverse("accounts:register"), {
            "first_name": "New", "last_name": "Leader", "username": "newleader",
            "email": "newleader@example.com", "purpose": "leader",
            "requested_ministries": [self.ministry.pk], "access_reason": "I volunteer.",
            "password1": "Long-Enough-Pass-42", "password2": "Long-Enough-Pass-42",
        })
        self.assertRedirects(response, reverse("core:portal"))
        user = User.objects.get(username="newleader")
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertFalse(user.is_staff)
        request = MinistryAccessRequest.objects.get(user=user)
        self.assertEqual(request.status, MinistryAccessRequest.Status.PENDING)
        self.assertEqual(list(request.ministries.all()), [self.ministry])
        self.assertEqual(user.led_ministries.count(), 0)

    def test_public_resource_is_explicit_opt_in(self):
        private = Resource.objects.create(
            title="Private", category="teaching", url="https://example.com/private", is_public=False
        )
        public = Resource.objects.create(
            title="Public", category="teaching", url="https://example.com/public", is_public=True
        )
        response = self.client.get(reverse("public_resources:list"))
        self.assertContains(response, public.title)
        self.assertNotContains(response, private.title)
        self.assertEqual(self.client.get(reverse("public_resources:open", args=[private.pk])).status_code, 404)

    def test_administrator_approval_assigns_only_requested_ministry(self):
        admin = User.objects.create_user("admin", password="Valid-Test-Pass-42", role=User.Role.ADMIN)
        member = User.objects.create_user("member", password="Valid-Test-Pass-42")
        other = Ministry.objects.create(name="Choir Ministry")
        access_request = MinistryAccessRequest.objects.create(user=member)
        access_request.ministries.add(self.ministry)
        self.client.force_login(admin)
        response = self.client.post(
            reverse("accounts:access_request_review", args=[access_request.pk]), {"decision": "approve"}
        )
        self.assertRedirects(response, reverse("accounts:access_requests"))
        member.refresh_from_db()
        access_request.refresh_from_db()
        self.assertEqual(member.role, User.Role.LEADER)
        self.assertTrue(member.led_ministries.filter(pk=self.ministry.pk).exists())
        self.assertFalse(member.led_ministries.filter(pk=other.pk).exists())
        self.assertFalse(member.is_staff)
        self.assertEqual(access_request.status, MinistryAccessRequest.Status.APPROVED)

    def test_leader_profile_and_inquiry_actions_are_ministry_scoped(self):
        leader = User.objects.create_user("leader", password="Valid-Test-Pass-42", role=User.Role.LEADER)
        leader.led_ministries.add(self.ministry)
        other = Ministry.objects.create(name="Media Ministry")
        inquiry = MinistryInquiry.objects.create(
            ministry=self.ministry, kind="join", name="Visitor", email="v@example.com", message="Interested"
        )
        self.client.force_login(leader)
        response = self.client.post(reverse("ministries:profile_edit", args=[self.ministry.slug]), {
            "description": "Updated public description", "mission": "Mission", "serves": "Families",
            "regular_activities": "Confirmed activities", "participation": "Contact us",
            "cash_app": "BethelYouth", "zelle": "youth@example.com",
        })
        self.assertRedirects(response, self.ministry.get_absolute_url())
        self.ministry.refresh_from_db()
        self.assertEqual(self.ministry.description, "Updated public description")
        self.assertEqual(self.ministry.cash_app, "$BethelYouth")
        self.assertEqual(self.ministry.zelle, "youth@example.com")
        self.assertEqual(
            self.client.post(reverse("ministries:profile_edit", args=[other.slug]), {}).status_code, 403
        )
        self.client.post(
            reverse("ministries:inquiry_status", args=[self.ministry.slug, inquiry.pk]), {"status": "contacted"}
        )
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, "contacted")

    def test_only_opted_in_activities_are_public(self):
        from datetime import date
        from .models import Activity

        Activity.objects.create(ministry=self.ministry, title="Private notes", date=date.today(), is_public=False)
        Activity.objects.create(
            ministry=self.ministry, title="Community gathering", date=date.today(), summary="A public recap.",
            is_public=True,
        )
        response = self.client.get(reverse("core:public_activities"))
        self.assertContains(response, "Community gathering")
        self.assertNotContains(response, "Private notes")
