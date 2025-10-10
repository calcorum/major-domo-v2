# Discord Bot v2.0 - Pre-Launch Roadmap

**Last Updated:** January 2025
**Target Launch:** TBD
**Current Status:** Core functionality complete including trading system, remaining utility commands needed

## 🎯 Overview

This document outlines the remaining functionality required before the Discord Bot v2.0 can be launched to replace the current bot. All core league management features are complete - this roadmap focuses on utility commands, integrations, and user experience enhancements.

## ✅ Completed Core Features

- **Player Information** (`/player`) - Comprehensive player cards with stats
- **Team Management** (`/team`, `/teams`, `/roster`) - Team information and roster breakdown
- **League Operations** (`/league`, `/standings`, `/schedule`) - League-wide information
- **Transaction Management** (`/mymoves`, `/legal`) - Player transaction tracking
- **Trading System** (`/trade`) - Full interactive trading with validation and dedicated channels
- **Voice Channels** (`/voice-channel`) - Automatic gameplay channel creation with cleanup
- **Custom Commands** (`/custom-command`) - User-created custom text commands
- **Admin Commands** - League administration and management tools
- **Background Services** - Automated cleanup, monitoring, and maintenance

## 🚧 Remaining Pre-Launch Requirements

### 🔧 Critical Fixes Required

#### 1. Custom Command Backend Support **✅ COMPLETED**
- **Status**: Complete and functional
- **Implementation**: Custom commands system fully operational
- **Features**: Users can create/manage custom text commands
- **Files**: `commands/custom_commands/`, `services/custom_command_service.py`
- **Completed**: January 2025

### 🎮 Utility Commands

#### 2. Weather Command **✅ COMPLETED**
- **Command**: `/weather [team_abbrev]`
- **Status**: Complete and fully functional
- **Implementation**: Ballpark weather rolling system for gameplay
- **Features Implemented**:
  - Smart team resolution (explicit param → channel name → user owned team)
  - Season display (Spring/Summer/Fall based on week)
  - Time of day logic (division weeks, games played tracking)
  - D20 weather roll with formatted display
  - Stadium image and team color styling
- **Completed**: January 2025

#### 3. Charts Display System **✅ COMPLETED**
- **Command**: `/charts <chart-name>`
- **Status**: Complete and fully functional
- **Implementation**: Chart display and management system
- **Features Implemented**:
  - Autocomplete chart selection with category display
  - Multi-image chart support
  - JSON-based chart library (12 charts migrated from legacy bot)
  - Admin commands for chart management (add, remove, list, update)
  - Category organization (gameplay, defense, reference, stats)
  - Proper embed formatting with descriptions
- **Data Storage**: `storage/charts.json` with JSON persistence
- **Completed**: January 2025

#### 4. Custom Help System **✅ COMPLETED**
- **Commands**: `/help [topic]`, `/help-create`, `/help-edit`, `/help-delete`, `/help-list`
- **Status**: Complete and ready for deployment (requires database migration)
- **Description**: Comprehensive help system for league documentation, resources, FAQs, and guides
- **Features Implemented**:
  - Create/edit/delete help topics (admin + "Help Editor" role)
  - Categorized help library (rules, guides, resources, info, faq)
  - Autocomplete for topic discovery
  - Markdown-formatted content
  - View tracking and analytics
  - Soft delete with restore capability
  - Full audit trail (who created, who modified)
  - Interactive modals for creation/editing
  - Paginated list views
  - Permission-based access control
- **Data Storage**: PostgreSQL table `help_commands` via API
- **Replaces**: Planned `/links` command (more flexible solution)
- **Documentation**: See `commands/help/README.md` and `.claude/DATABASE_MIGRATION_HELP_COMMANDS.md`
- **Completed**: January 2025

### 🖼️ User Profile Management

#### 5. Image Management Commands
- **Commands**:
  - `/set-headshot <url>` - Set player headshot image
  - `/set-fancy-card <url>` - Set player fancy card image
- **Description**: Allow users to customize their player profile images
- **Features**:
  - Image URL validation
  - Size/format checking
  - Preview in response embed
  - Integration with existing player card system
- **Permissions**: User can only modify their own player images
- **Database**: Update player image URLs in database
- **Estimated Effort**: 2-3 hours

### 🎯 Gaming & Entertainment

#### 6. Meme Commands
- **Primary Command**: `/lastsoak`
- **Description**: Classic SBA meme commands for community engagement
- **Features**:
  - `/lastsoak` - Display last player to be "soaked" (statistical reference)
  - Embed formatting with player info and stats
  - Historical tracking of events
- **Data Source**: Database queries for recent player performance
- **Estimated Effort**: 1-2 hours

#### 7. Scouting System
- **Command**: `/scout [options]`
- **Description**: Weighted dice rolling system for scouting mechanics
- **Features**:
  - Multiple dice configurations
  - Weighted probability systems
  - Result interpretation and display
  - Historical scouting logs
- **Complexity**: Custom probability algorithms
- **Estimated Effort**: 3-4 hours

#### 8. Trading System **✅ COMPLETED**
- **Command**: `/trade [parameters]`
- **Status**: Complete and fully functional
- **Implementation**: Full interactive trading system with comprehensive features
- **Features Implemented**:
  - Trade proposal system with interactive UI
  - Multi-party trade support (up to 2 teams)
  - Trade validation (roster limits, salary caps, sWAR tracking)
  - Trade history and tracking
  - Integration with transaction system
  - Dedicated trade discussion channels with smart permissions
  - Pre-existing transaction awareness for accurate projections
- **Completed**: January 2025

## 📋 Implementation Priority

### Phase 1: Critical Fixes ✅ COMPLETED
1. ✅ **Custom Command Backend** - Fixed and fully operational (January 2025)

### Phase 2: Core Utilities
2. ✅ **Weather Command** - Complete with smart team resolution (January 2025)
3. ✅ **Charts System** - Complete with admin management and 12 charts (January 2025)
4. ✅ **Help System** - Complete with comprehensive help topics and CRUD capabilities (January 2025)

### Phase 3: User Features (Week 2)
5. **Image Management** - User profile customization
6. **Meme Commands** - Community engagement

### Phase 4: Advanced Features
7. **Scout Command** - Complex gaming mechanics
8. ✅ **Trade Command** - Complete with comprehensive features (January 2025)

## 🏗️ Architecture Considerations

### Command Organization
```
commands/
├── utilities/
│   ├── weather.py          # Weather command
│   ├── charts.py           # Charts display system
│   └── links.py            # Resource links system
├── profile/
│   └── images.py           # Image management commands
├── gaming/
│   ├── memes.py            # Meme commands (lastsoak)
│   ├── scout.py            # Scouting dice system
│   └── trading.py          # Trade management system
```

### Service Layer Requirements
- **WeatherService**: API integration for weather data
- **ResourceService**: Chart and link management
- **ProfileService**: User image management
- **ScoutingService**: Dice mechanics and probability
- ✅ **TradingService**: Complete - complex trade logic and validation implemented (January 2025)

### Database Schema Updates
- ✅ **Custom commands**: Complete and operational (January 2025)
- **Resources**: Chart/link storage tables
- **Player images**: Image URL fields
- ✅ **Trades**: Complete - trade proposal and history tables implemented (January 2025)

## 🧪 Testing Requirements

### Test Coverage Goals
- **Unit Tests**: All new services and commands
- **Integration Tests**: Database interactions, API calls
- **End-to-End Tests**: Complete command workflows
- **Performance Tests**: Database query optimization

### Test Categories by Feature
- **Weather**: API mocking, error handling, rate limiting
- **Charts/Links**: URL validation, admin permissions
- **Images**: URL validation, permission checks
- ✅ **Trading**: Complete - complex multi-user scenarios, validation logic all tested (January 2025)

## 📚 Documentation Updates

### User-Facing Documentation
- Command reference updates
- Feature guides for complex commands (trading, scouting)
- Admin guides for resource management

### Developer Documentation
- Service architecture documentation
- Database schema updates
- API integration guides

## ⚡ Performance Considerations

### Database Optimization
- Index requirements for new tables
- Query optimization for complex operations (trading)
- Cache invalidation strategies

### API Rate Limiting
- Weather API rate limits and caching
- Image URL validation and caching
- Error handling for external services

## 🚀 Launch Checklist

### Pre-Launch Validation
- [ ] All commands functional and tested
- [ ] Database migrations completed
- [ ] API keys and external services configured
- [ ] Error handling and logging verified
- [ ] Performance benchmarks met

### Deployment Requirements
- [ ] Environment variables configured
- [ ] External API credentials secured
- [ ] Database backup procedures tested
- [ ] Rollback plan documented
- [ ] User migration strategy defined

## 📊 Success Metrics

### Functionality Metrics
- **Command Success Rate**: >95% successful command executions
- **Response Time**: <2 seconds average response time
- **Error Rate**: <5% error rate across all commands

### User Engagement
- **Command Usage**: Track usage patterns for new commands
- **User Adoption**: Monitor migration from old bot to new bot
- **Community Feedback**: Collect feedback on new features

## 🔮 Post-Launch Enhancements

### Future Considerations (Not Pre-Launch Blockers)
- Advanced trading features (trade deadline management)
- Enhanced scouting analytics and reporting
- Weather integration with game scheduling
- Mobile-optimized command interfaces
- Advanced user profile customization

---

## 📞 Development Notes

### Current Bot Architecture Strengths
- **Robust Service Layer**: Clean separation of concerns
- **Comprehensive Testing**: 44+ tests with good coverage
- **Modern Discord.py**: Latest slash command implementation
- **Error Handling**: Comprehensive error handling and logging
- **Documentation**: Thorough README files and architectural docs

### Technical Debt Considerations
- ✅ **Custom Commands**: Resolved - backend fully operational (January 2025)
- ✅ **Trading System**: Complete with comprehensive validation (January 2025)
- **Database Performance**: Monitor query performance with new features
- **External Dependencies**: Manage API dependencies and rate limits
- **Cache Management**: Implement caching for expensive operations

### Resource Requirements
- **Development Time**: ~6-9 hours remaining (reduced from 20-25 hours)
  - ✅ Custom Commands: Complete (saved 2-3 hours)
  - ✅ Trading System: Complete (saved 6-8 hours)
  - ✅ Weather Command: Complete (saved 3-4 hours)
  - ✅ Charts System: Complete (saved 2-3 hours)
  - ✅ Help System: Complete (saved 2-3 hours)
  - Remaining: Images (2-3h), Memes (1-2h), Scout (3-4h)
- **API Costs**: None required (weather is gameplay dice rolling, not real weather)
- **Database Storage**: Minimal increase for new features
- **Hosting Resources**: Current infrastructure sufficient

---

**Target Timeline: 1 week for complete pre-launch readiness**
**Next Steps: Implement user features (image management, meme commands) and scouting system**