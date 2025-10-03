# Use the official Node.js image
FROM node:20-slim

# Set the working directory
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Set build-time environment variables for Vue.js
ENV VUE_APP_API_URL=https://dev.missingtable.com
ENV VUE_APP_SUPABASE_URL=https://ppgxasqgqbnauvxozmjw.supabase.co
ENV VUE_APP_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBwZ3hhc3FncWJuYXV2eG96bWp3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTE0ODQ5MTAsImV4cCI6MjA2NzA2MDkxMH0.5R1E-CpsZJU_4tRaaYrq4P00IhIrsIjqo0zQuX-rBHQ
ENV VUE_APP_DISABLE_SECURITY=true

# Build the application
RUN npm run build

# Install serve to serve the built app
RUN npm install -g serve

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["serve", "-s", "dist", "-l", "8080"]