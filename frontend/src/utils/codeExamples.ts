// Language dropdown fix and extended examples
export const codeExamples = {
  python: `def calculate_average(numbers):
    total = sum(numbers)
    return total / len(numbers)

# Potential issue: division by zero
average = calculate_average([])
print(average)`,

  javascript: `function validateEmail(email) {
    // Security issue: weak validation
    return email.includes('@');
}

// Performance issue: inefficient loop
function findUser(users, targetId) {
    for(let i = 0; i < users.length; i++) {
        if(users[i].id == targetId) { // Bug: loose equality
            return users[i];
        }
    }
}`,

  java: `public class Calculator {
    public double divide(int a, int b) {
        // Bug: no zero check
        return a / b;
    }
    
    // Security issue: SQL injection vulnerability
    public User getUser(String userId) {
        String query = "SELECT * FROM users WHERE id = '" + userId + "'";
        return executeQuery(query);
    }
}`,

  cpp: `#include <iostream>
#include <vector>

class DataProcessor {
public:
    int* processData(std::vector<int>& data) {
        int* result = new int[data.size()]; // Memory leak potential
        
        for(int i = 0; i <= data.size(); i++) { // Buffer overflow bug
            result[i] = data[i] * 2;
        }
        
        return result; // Caller must delete, not documented
    }
};`,

  go: `package main

import (
    "fmt"
    "net/http"
)

func handleRequest(w http.ResponseWriter, r *http.Request) {
    userInput := r.URL.Query().Get("data")
    
    // Security issue: XSS vulnerability
    fmt.Fprintf(w, "<h1>Hello %s</h1>", userInput)
    
    // Performance issue: no connection pooling
    resp, err := http.Get("http://api.example.com/data")
    if err != nil {
        return // Bug: not handling error properly
    }
    defer resp.Body.Close()
}`,

  rust: `use std::collections::HashMap;

fn process_user_data(data: &str) -> Result<String, &'static str> {
    // Performance issue: unnecessary cloning
    let mut map: HashMap<String, String> = HashMap::new();
    
    for line in data.lines() {
        let parts: Vec<&str> = line.split(',').collect();
        // Bug: potential panic on index access
        map.insert(parts[0].to_string(), parts[1].to_string());
    }
    
    Ok(format!("{:?}", map))
}`,

  typescript: `interface User {
    id: number;
    email: string;
    password: string; // Security issue: storing password in interface
}

class UserService {
    private users: User[] = [];
    
    // Bug: synchronous operation in async context
    async getUser(id: number): Promise<User | null> {
        return this.users.find(user => user.id == id) || null; // Type coercion bug
    }
    
    // Security issue: no input validation
    createUser(userData: any): User {
        return {
            id: Math.random(), // Bug: non-unique ID generation
            email: userData.email,
            password: userData.password
        } as User;
    }
}`,

  c: `#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int* process_numbers(int* array, int size) {
    // Bug: potential memory leak
    int* result = malloc(size * sizeof(int));
    
    for(int i = 0; i <= size; i++) { // Bug: buffer overflow
        result[i] = array[i] * 2;
    }
    
    return result; // Caller must free, not documented
}

// Security issue: buffer overflow vulnerability
void copy_string(char* dest, char* src) {
    strcpy(dest, src); // No bounds checking
}`,

  php: `<?php
class UserManager {
    private $db_connection;
    
    // Security issue: SQL injection vulnerability
    public function getUser($userId) {
        $query = "SELECT * FROM users WHERE id = " . $userId; // No sanitization
        return mysqli_query($this->db_connection, $query);
    }
    
    // Bug: password comparison using loose equality
    public function validateLogin($username, $password) {
        $user = $this->getUserByUsername($username);
        if ($user['password'] == $password) { // Should use password_verify()
            return true;
        }
        return false;
    }
    
    // Performance issue: N+1 query problem
    public function getUsersWithPosts() {
        $users = $this->getAllUsers();
        foreach($users as &$user) {
            $user['posts'] = $this->getPostsByUserId($user['id']); // Multiple queries
        }
        return $users;
    }
}
?>`,

  ruby: `class UserService
  def initialize
    @users = []
  end
  
  # Bug: potential division by zero
  def calculate_average_age(users)
    total_age = users.sum { |user| user[:age] }
    total_age / users.length # No check for empty array
  end
  
  # Security issue: mass assignment vulnerability
  def create_user(params)
    user = User.new(params) # No parameter filtering
    user.save
  end
  
  # Performance issue: N+1 query
  def users_with_posts
    User.all.map do |user|
      {
        user: user,
        posts: Post.where(user_id: user.id) # Individual query for each user
      }
    end
  end
  
  # Bug: method always returns nil
  def find_user_by_email(email)
    @users.each do |user|
      if user[:email] == email
        user # This doesn't return from the method
      end
    end
  end
end`
};

export const getLanguageDisplayName = (lang: string): string => {
  const names: Record<string, string> = {
    python: 'Python',
    javascript: 'JavaScript', 
    java: 'Java',
    cpp: 'C++',
    c: 'C',
    go: 'Go',
    rust: 'Rust',
    php: 'PHP',
    ruby: 'Ruby',
    typescript: 'TypeScript'
  };
  return names[lang] || lang;
};