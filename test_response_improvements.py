import unittest
from app import app, conversations, get_session, validate_response

from unittest.mock import patch

class TestBotImprovements(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Clear conversations before each test
        conversations.clear()

    @patch('app.get_gemini_response')
    @patch('app.get_openrouter_response')
    def test_session_creation(self, mock_or, mock_gemini):
        mock_gemini.return_value = "Hello there!"
        mock_or.return_value = "Hello there!"
        
        with self.app as client:
            response = client.post('/api/chat', json={'message': 'Hello'})
            data = response.get_json()
            
            self.assertIn('session_id', data)
            self.assertTrue(len(data['session_id']) > 0)
            self.assertIn(data['session_id'], conversations)

    @patch('app.get_gemini_response')
    def test_conversation_memory(self, mock_gemini):
        mock_gemini.return_value = "Nice to meet you."
        
        with self.app as client:
            # First message
            resp1 = client.post('/api/chat', json={'message': 'My name is Alice'})
            data1 = resp1.get_json()
            session_id = data1['session_id']
            
            # Verify added to history
            session = conversations[session_id]
            self.assertEqual(len(session.history), 2) # User + Bot
            self.assertEqual(session.history[0]['content'], 'My name is Alice')

            # Second message with session_id
            resp2 = client.post('/api/chat', json={
                'message': 'What is my name?',
                'session_id': session_id
            })
            
            # Verify history grew
            self.assertEqual(len(session.history), 4) # User + Bot + User + Bot

    def test_response_validation_scheduling(self):
        """Test that scheduling keywords trigger calendar embed."""
        # Case 1: Response already has it
        resp = validate_response("I want to book", "Sure! [CALENDAR_EMBED]")
        self.assertIn("[CALENDAR_EMBED]", resp)
        self.assertEqual(resp.count("[CALENDAR_EMBED]"), 1)

        # Case 2: Response missing it but user asked to schedule
        resp = validate_response("I want to schedule an appointment", "We can help with that.")
        self.assertIn("[CALENDAR_EMBED]", resp)
        self.assertTrue("choose a time" in resp.lower() or "calendar" in resp.lower())

    def test_response_validation_irrelevant(self):
        """Test that irrelevant queries don't trigger calendar."""
        resp = validate_response("What is 2+2?", "It is 4.")
        self.assertNotIn("[CALENDAR_EMBED]", resp)

    def test_response_validation_contextual(self):
        """Test that 'Yes' triggers calendar if bot previously offered to schedule."""
        from app import ConversationSession
        session = ConversationSession()
        session.add_message("user", "How much?")
        session.add_message("assistant", "It is $49. Would you like to schedule an assessment?")
        
        # User says "Yes" -> Bot response might be generic "Sure." initially
        # Validation should add calendar
        resp = validate_response("Yes please", "Sure thing.", session)
        self.assertIn("[CALENDAR_EMBED]", resp)
        self.assertTrue("works best" in resp.lower() or "here" in resp.lower())

if __name__ == '__main__':
    unittest.main()
