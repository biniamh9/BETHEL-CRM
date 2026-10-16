from django.db import migrations


OLD_NAME = "New Church Building Fund"
OLD_TAGLINE = "A permanent home for our families and the next generation."
OLD_STORY = """Since 2011, Bethel Eritrean Alliance Church has been a home for Eritrean and East African families across Metro Atlanta — in Atlanta, Tucker, Stone Mountain, Clarkston, Lilburn and Decatur. Today more than 100 members and 74 children, youth and young adults gather with us every week.

We have outgrown our rented space. Limited classrooms, tight scheduling and no room for counseling or youth programs mean we turn families away from programs they need. We currently pay about $2,000 a month in rent and own nothing we can build on.

Our members have already saved about $200,000 toward a permanent home. With your help we will buy a building with a main sanctuary, classrooms for children, a youth center, family counseling rooms and space for community workshops — a place that will serve the next generation.

Every gift, large or small, brings us closer. Thank you for standing with us."""

NEW_NAME = "Help Bethel Eritrean Church Build a Permanent Home"
NEW_TAGLINE = "A Home for Worship. A Place for Families. A Future for Our Children."
NEW_STORY = """Since 2011, Bethel Eritrean Alliance Church has faithfully served Eritrean families and the broader community in the Atlanta, Georgia area.

For more than 15 years, our church has been more than a place of Sunday worship. It has been a spiritual home where families gather in faith, children learn biblical values, young people receive encouragement and mentorship, and generations come together in fellowship and service.

As our congregation continues to grow, so does our need for a permanent place to worship and serve our community.

Today, we are taking an important step of faith toward purchasing our own church building in Stone Mountain, Georgia.

## Why We Need Your Support

Our vision is to establish a permanent church home that will allow us to:

- Provide a welcoming sanctuary for worship and prayer.
- Create dedicated classrooms for children's Bible education.
- Expand youth discipleship and mentorship programs.
- Offer space for family fellowship and community gatherings.
- Preserve our Eritrean Christian heritage while serving future generations.
- Build a lasting foundation for our church's mission.

## Our Building Fund Campaign

We are raising funds to support the purchase of our new church property and the essential expenses needed to prepare the building for worship and ministry activities.

Every contribution, regardless of size, brings us closer to securing a permanent home for our congregation.

Your donation is more than a contribution toward a building. It is an investment in faith, family, community, and future generations.

## How You Can Help

1. Make a donation of any amount.
2. Share this campaign with friends, family, and your community.
3. Invite others who believe in our mission to support this effort.
4. Keep our church in your prayers as we move forward.

We are deeply grateful for every prayer, donation, and act of encouragement.

Together, let us build a home where faith grows, families are strengthened, and future generations are inspired.

With gratitude,
Bethel Eritrean Alliance Church
Atlanta, Georgia"""


def update_campaign(apps, schema_editor):
    Campaign = apps.get_model("fundraising", "Campaign")
    campaign = Campaign.objects.filter(slug="new-church-building").first()
    if not campaign:
        return
    updates = {}
    if campaign.name == OLD_NAME:
        updates["name"] = NEW_NAME
    if campaign.tagline == OLD_TAGLINE:
        updates["tagline"] = NEW_TAGLINE
    if campaign.story == OLD_STORY:
        updates["story"] = NEW_STORY
    if updates:
        Campaign.objects.filter(pk=campaign.pk).update(**updates)


def restore_campaign(apps, schema_editor):
    Campaign = apps.get_model("fundraising", "Campaign")
    campaign = Campaign.objects.filter(slug="new-church-building").first()
    if not campaign:
        return
    updates = {}
    if campaign.name == NEW_NAME:
        updates["name"] = OLD_NAME
    if campaign.tagline == NEW_TAGLINE:
        updates["tagline"] = OLD_TAGLINE
    if campaign.story == NEW_STORY:
        updates["story"] = OLD_STORY
    if updates:
        Campaign.objects.filter(pk=campaign.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [("fundraising", "0001_initial")]
    operations = [migrations.RunPython(update_campaign, restore_campaign)]
