from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.core.models import CustomerSupportTicket


class AdminReportAgentTests(TestCase):
    def test_active_agent_run_claim_prevents_duplicate_delivery(self):
        from apps.agents.models import AgentRun
        from apps.agents.tasks import _claim_agent_run

        first, first_claimed = _claim_agent_run("duplicate-delivery-test", "test_agent", "task-1")
        duplicate, duplicate_claimed = _claim_agent_run("duplicate-delivery-test", "test_agent", "task-2")

        self.assertTrue(first_claimed)
        self.assertFalse(duplicate_claimed)
        self.assertEqual(first.pk, duplicate.pk)
        self.assertEqual(AgentRun.objects.get(pk=first.pk).attempts, 1)

    def test_report_agents_return_structured_findings_and_summary(self):
        from apps.agents.services import run_report_agents

        findings, summary = run_report_agents(report_id=1)

        self.assertEqual(
            set(findings), {
                "catalog", "commerce", "site_analytics", "inventory_operations",
                "accounting", "support_routing", "safety_reliability", "recommendation_quality",
                "database_backup", "email_support", "site_health_audit", "administrator_summary",
            }
        )
        self.assertIn("available_products", findings["catalog"])
        self.assertIn("orders_last_7_days", findings["commerce"])
        self.assertIn("orders_month_to_date", findings["commerce"])
        self.assertIn("untracked_products", findings["inventory_operations"])
        self.assertIn("settled_payment_count", findings["accounting"])
        self.assertIn("settled_amount_by_currency_today", findings["accounting"])
        self.assertIn("settled_amount_by_currency_month_to_date", findings["accounting"])
        self.assertIn("settled_amount_by_currency_year_to_date", findings["accounting"])
        self.assertIn("settled_payment_count_year_to_date", findings["accounting"])
        self.assertIn("model_failures_last_7_days", findings["safety_reliability"])
        self.assertIn("searches", findings["recommendation_quality"])
        self.assertIn("empty_result_rate", findings["recommendation_quality"])
        self.assertFalse(findings["email_support"]["mailbox_connected"])
        self.assertIn("backup_healthy", findings["administrator_summary"])
        self.assertIn("7-day admin report", summary)

    def test_report_agents_do_not_depend_on_llm_availability(self):
        from apps.agents.services import run_report_agents

        findings, summary = run_report_agents(report_id=1)

        self.assertIsInstance(findings, dict)
        self.assertIsInstance(summary, str)
        self.assertNotIn("placeholder", summary.lower())

    def test_agents_accept_integer_report_id(self):
        from apps.agents.services import run_report_agents

        findings, summary = run_report_agents(report_id=123)

        self.assertIsInstance(findings, dict)
        self.assertIsInstance(summary, str)

    def test_support_agent_routes_and_saves_a_reviewable_draft(self):
        from apps.agents.services import SupportDraftAgent

        user = get_user_model().objects.create_user(
            username="ticket-customer", email="customer@example.test", password="safe-test-password"
        )
        ticket = CustomerSupportTicket.objects.create(
            user=user, subject="Monitor order", message="Please help track my monitor delivery."
        )

        SupportDraftAgent().process(ticket.pk)

        ticket.refresh_from_db()
        self.assertEqual(ticket.department, CustomerSupportTicket.Department.INVENTORY)
        self.assertIn("order number", ticket.agent_draft)
        self.assertFalse(ticket.auto_response_sent)

    def test_database_backup_command_writes_a_compressed_django_fixture(self):
        import gzip
        import json
        import tempfile
        from pathlib import Path
        from django.core.management import call_command
        from django.test import override_settings

        with tempfile.TemporaryDirectory() as directory:
            with override_settings(BACKUP_DIR=Path(directory)):
                call_command("backup_shop_database", verbosity=0)
                backups = list(Path(directory).glob("riva-db-*.json.gz"))
                self.assertEqual(len(backups), 1)
                with gzip.open(backups[0], "rt", encoding="utf-8") as backup_file:
                    records = json.load(backup_file)
                self.assertIsInstance(records, list)
