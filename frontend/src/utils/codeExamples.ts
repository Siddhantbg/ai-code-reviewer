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
}`
};

export const getLanguageDisplayName = (lang: string): string => {
  const names: Record<string, string> = {
    python: 'Python',
    javascript: 'JavaScript', 
    java: 'Java',
    cpp: 'C++',
    go: 'Go',
    rust: 'Rust',
    typescript: 'TypeScript'
  };
  return names[lang] || lang;
};