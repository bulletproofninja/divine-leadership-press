import requests
import sys
import json
from datetime import datetime

class DivineLeadershipPressAPITester:
    def __init__(self, base_url="https://editorial-studio-19.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user_id = None
        self.document_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            
            if success:
                self.log_test(name, True)
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                self.log_test(name, False, f"Expected {expected_status}, got {response.status_code}")
                return False, {}

        except Exception as e:
            self.log_test(name, False, f"Error: {str(e)}")
            return False, {}

    def test_api_health(self):
        """Test API health endpoint"""
        print("\n🔍 Testing API Health...")
        success, response = self.run_test(
            "API Health Check",
            "GET",
            "",
            200
        )
        return success

    def test_user_registration(self):
        """Test user registration"""
        print("\n🔍 Testing User Registration...")
        test_email = f"testuser_{datetime.now().strftime('%H%M%S')}@example.com"
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data={
                "email": test_email,
                "name": "Test User",
                "password": "TestPass123!"
            }
        )
        
        if success and 'token' in response:
            self.token = response['token']
            self.user_id = response['user']['id']
            print(f"   Token received: {self.token[:20]}...")
            return True
        return False

    def test_user_login(self):
        """Test user login with existing credentials"""
        print("\n🔍 Testing User Login...")
        # First register a user
        test_email = f"logintest_{datetime.now().strftime('%H%M%S')}@example.com"
        
        # Register
        reg_success, reg_response = self.run_test(
            "Registration for Login Test",
            "POST",
            "auth/register",
            200,
            data={
                "email": test_email,
                "name": "Login Test User",
                "password": "TestPass123!"
            }
        )
        
        if not reg_success:
            return False
            
        # Now test login
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data={
                "email": test_email,
                "password": "TestPass123!"
            }
        )
        
        return success and 'token' in response

    def test_get_user_profile(self):
        """Test getting current user profile"""
        print("\n🔍 Testing User Profile...")
        success, response = self.run_test(
            "Get User Profile",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_create_document(self):
        """Test document creation"""
        print("\n🔍 Testing Document Creation...")
        success, response = self.run_test(
            "Create Document",
            "POST",
            "documents",
            200,
            data={
                "title": "Test Book",
                "content": "This is a test book content.",
                "format": "6x9"
            }
        )
        
        if success and 'id' in response:
            self.document_id = response['id']
            print(f"   Document ID: {self.document_id}")
            return True
        return False

    def test_get_documents(self):
        """Test getting user documents"""
        print("\n🔍 Testing Get Documents...")
        success, response = self.run_test(
            "Get Documents",
            "GET",
            "documents",
            200
        )
        return success

    def test_get_single_document(self):
        """Test getting a single document"""
        if not self.document_id:
            self.log_test("Get Single Document", False, "No document ID available")
            return False
            
        print("\n🔍 Testing Get Single Document...")
        success, response = self.run_test(
            "Get Single Document",
            "GET",
            f"documents/{self.document_id}",
            200
        )
        return success

    def test_update_document(self):
        """Test document update"""
        if not self.document_id:
            self.log_test("Update Document", False, "No document ID available")
            return False
            
        print("\n🔍 Testing Document Update...")
        success, response = self.run_test(
            "Update Document",
            "PUT",
            f"documents/{self.document_id}",
            200,
            data={
                "title": "Updated Test Book",
                "content": "This is updated content with more text.",
                "metadata": {
                    "author": "Test Author",
                    "isbn": "978-3-16-148410-0",
                    "genre": "Fiction"
                }
            }
        )
        return success

    def test_document_versions(self):
        """Test getting document versions"""
        if not self.document_id:
            self.log_test("Get Document Versions", False, "No document ID available")
            return False
            
        print("\n🔍 Testing Document Versions...")
        success, response = self.run_test(
            "Get Document Versions",
            "GET",
            f"documents/{self.document_id}/versions",
            200
        )
        return success

    def test_add_comment(self):
        """Test adding comment to document"""
        if not self.document_id:
            self.log_test("Add Comment", False, "No document ID available")
            return False
            
        print("\n🔍 Testing Add Comment...")
        success, response = self.run_test(
            "Add Comment",
            "POST",
            f"documents/{self.document_id}/comments",
            200,
            data={
                "content": "This is a test comment for the document."
            }
        )
        return success

    def test_get_comments(self):
        """Test getting document comments"""
        if not self.document_id:
            self.log_test("Get Comments", False, "No document ID available")
            return False
            
        print("\n🔍 Testing Get Comments...")
        success, response = self.run_test(
            "Get Comments",
            "GET",
            f"documents/{self.document_id}/comments",
            200
        )
        return success

    def test_export_document(self):
        """Test document export"""
        if not self.document_id:
            self.log_test("Export Document", False, "No document ID available")
            return False
            
        print("\n🔍 Testing Document Export...")
        success, response = self.run_test(
            "Export Document (PDF)",
            "POST",
            f"documents/{self.document_id}/export?format=pdf",
            200
        )
        return success

    def test_kdp_integration(self):
        """Test KDP publishing integration (mocked)"""
        if not self.document_id:
            self.log_test("KDP Integration", False, "No document ID available")
            return False
            
        print("\n🔍 Testing KDP Integration...")
        success, response = self.run_test(
            "KDP Integration",
            "POST",
            f"integrations/kdp?document_id={self.document_id}",
            200
        )
        return success

    def test_lulu_integration(self):
        """Test LULU publishing integration (mocked)"""
        if not self.document_id:
            self.log_test("LULU Integration", False, "No document ID available")
            return False
            
        print("\n🔍 Testing LULU Integration...")
        success, response = self.run_test(
            "LULU Integration",
            "POST",
            f"integrations/lulu?document_id={self.document_id}",
            200
        )
        return success

    def test_file_upload(self):
        """Test file upload functionality"""
        print("\n🔍 Testing File Upload...")
        
        # Create a test text file
        test_content = "This is a test document for upload functionality.\n\nIt contains multiple paragraphs to test the upload feature."
        
        try:
            url = f"{self.api_url}/documents/upload"
            headers = {'Authorization': f'Bearer {self.token}'}
            
            files = {'file': ('test_upload.txt', test_content, 'text/plain')}
            
            response = requests.post(url, files=files, headers=headers, timeout=10)
            
            success = response.status_code == 200
            
            if success:
                self.log_test("File Upload", True)
                return True
            else:
                self.log_test("File Upload", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("File Upload", False, f"Error: {str(e)}")
            return False

    def test_delete_document(self):
        """Test document deletion"""
        if not self.document_id:
            self.log_test("Delete Document", False, "No document ID available")
            return False
            
        print("\n🔍 Testing Document Deletion...")
        success, response = self.run_test(
            "Delete Document",
            "DELETE",
            f"documents/{self.document_id}",
            200
        )
        return success

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Divine Leadership Press API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)

        # Test sequence
        tests = [
            self.test_api_health,
            self.test_user_registration,
            self.test_user_login,
            self.test_get_user_profile,
            self.test_create_document,
            self.test_get_documents,
            self.test_get_single_document,
            self.test_update_document,
            self.test_document_versions,
            self.test_add_comment,
            self.test_get_comments,
            self.test_export_document,
            self.test_kdp_integration,
            self.test_lulu_integration,
            self.test_file_upload,
            self.test_delete_document
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                print(f"❌ {test.__name__} - Unexpected error: {str(e)}")
                self.tests_run += 1

        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    tester = DivineLeadershipPressAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())