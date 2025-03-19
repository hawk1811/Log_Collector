# Add this import to the existing imports in cli_main.py
from log_collector.updater import check_for_updates, restart_application

# Replace the existing _show_main_menu method with this:
    def _show_main_menu(self):
        """Display main menu and handle commands."""
        clear()  # Ensure screen is cleared
        self._print_header()
        
        # Show logged in user if authenticated
        if self.authenticated and self.current_user:
            print(f"Logged in as: {Fore.GREEN}{self.current_user}{ColorStyle.RESET_ALL}")
        
        print("\nMain Menu:")
        print("1. Add New Source")
        print("2. Manage Sources")
        print("3. Health Check Configuration")
        print("4. View Status")
        
        # Add change password option if auth_manager is available
        if self.auth_manager and self.authenticated:
            print("5. Change Password")
            print("6. Check for Updates")
            print("7. Exit")
            max_option = 7
        else:
            print("5. Check for Updates")
            print("6. Exit")
            max_option = 6
        
        choice = prompt(
            HTML(f"<ansicyan>Choose an option (1-{max_option}): </ansicyan>"),
            style=self.prompt_style
        )
        
        if choice == "1":
            add_source(self.source_manager, self.processor_manager, self.listener_manager, self)
        elif choice == "2":
            manage_sources(self.source_manager, self.processor_manager, self.listener_manager, self, self.aggregation_manager)
        elif choice == "3":
            configure_health_check(self.health_check, self)
        elif choice == "4":
            view_status(self.source_manager, self.processor_manager, self.listener_manager, self.health_check, self.aggregation_manager, self.current_user)
        elif choice == "5" and self.auth_manager and self.authenticated:
            # Change password
            change_password_screen(self.auth_manager, self.current_user, False, self)
        elif (choice == "6" and self.auth_manager and self.authenticated) or (choice == "5" and (not self.auth_manager or not self.authenticated)):
            # Check for updates
            should_restart = check_for_updates(self)
            if should_restart:
                print(f"\n{Fore.GREEN}Update successful! The application will now restart...{ColorStyle.RESET_ALL}")
                print(f"{Fore.CYAN}Please wait...{ColorStyle.RESET_ALL}")
                time.sleep(2)  # Give user time to read the message
                
                self._clean_exit()
                # After clean exit, restart the application
                restart_application()
        elif (choice == "7" and self.auth_manager and self.authenticated) or (choice == "6" and (not self.auth_manager or not self.authenticated)):
            self._exit_application()
            # If we return here, it means the user canceled the exit
            return
        else:
            print(f"{Fore.RED}Invalid choice. Please try again.{ColorStyle.RESET_ALL}")
