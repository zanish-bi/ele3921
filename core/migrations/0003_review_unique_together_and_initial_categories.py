from django.db import migrations


INITIAL_CATEGORIES = [
    ("Design", "Graphic design, UI/UX, branding, and visual assets"),
    ("Programming", "Web development, apps, scripts, and software"),
    ("Tutoring", "Academic subjects, test prep, and skill coaching"),
    ("Writing", "Essays, copywriting, technical writing, and editing"),
    ("Video & Animation", "Video editing, motion graphics, and animation"),
    ("Translation", "Document translation and multilingual content"),
    ("Marketing", "Social media, SEO, and digital marketing"),
    ("Data & Research", "Data analysis, surveys, and research assistance"),
]


def add_initial_categories(apps, schema_editor):
    Category = apps.get_model("core", "Category")
    for name, description in INITIAL_CATEGORIES:
        Category.objects.get_or_create(name=name, defaults={"description": description})


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_alter_userprofile_user"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="review",
            unique_together={("contract", "reviewer")},
        ),
        migrations.RunPython(add_initial_categories, migrations.RunPython.noop),
    ]
