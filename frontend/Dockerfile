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

# Build arguments (must be provided at build time)
# Note: Supabase anon key is PUBLIC by design (protected by RLS policies)
ARG VUE_APP_API_URL
ARG VUE_APP_SUPABASE_URL
ARG VUE_APP_SUPABASE_ANON_KEY
ARG VUE_APP_DISABLE_SECURITY

# Set as environment variables for Vue.js build
ENV VUE_APP_API_URL=$VUE_APP_API_URL
ENV VUE_APP_SUPABASE_URL=$VUE_APP_SUPABASE_URL
ENV VUE_APP_SUPABASE_ANON_KEY=$VUE_APP_SUPABASE_ANON_KEY
ENV VUE_APP_DISABLE_SECURITY=$VUE_APP_DISABLE_SECURITY

# Build the application
RUN npm run build

# Install serve to serve the built app
RUN npm install -g serve

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["serve", "-s", "dist", "-l", "8080"]